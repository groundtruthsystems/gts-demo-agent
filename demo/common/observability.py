"""Reusable OpenTelemetry + Keycloak observability bootstrap.

This module packages the OTLP log/trace export setup, Keycloak OAuth2
client-credentials authentication, and the Langfuse client wiring into a small
set of classes so the same observability stack can be reused as a library
across services rather than living inline in a single entrypoint.

Typical use:

    obs = OtelObservability.from_config(config_data,
                                        service_name="gts-echo",
                                        service_version="1.2.3")
    tracer = obs.init()                     # OTLP logs+traces exporting; LlamaIndex instrumented
    langfuse = obs.build_langfuse_client()  # optional; authenticated the same way

Authentication model
--------------------
When a ``control_plane`` (Keycloak) configuration is supplied, every outbound
call — OTLP log export, OTLP trace export, and the Langfuse REST/transport
client — carries a Keycloak bearer token obtained via the client_credentials
grant. The token is fetched lazily, cached, and refreshed shortly before it
expires, and it is re-read on *every* request so a long-running process never
sends an expired token. When Keycloak is not configured, export falls back to
Langfuse Basic Auth derived from the project public/secret keys.
"""
from __future__ import annotations

import atexit
import base64
import logging
import threading
import time
from dataclasses import dataclass
from typing import Dict, Optional

import httpx
import requests.auth

from opentelemetry._logs import set_logger_provider
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import SimpleLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.logging import LoggingInstrumentor

# Langfuse's OTLP signal paths; overridable for other OTLP backends.
DEFAULT_LOGS_PATH = "/api/public/otel/v1/logs"
DEFAULT_TRACES_PATH = "/api/public/otel/v1/traces"

_DEFAULT_HTTP_TIMEOUT = 20.0


class KeycloakTokenProvider:
    """Fetches and caches OAuth2 access tokens via the client_credentials grant.

    Thread-safe: the token is cached in-process and refreshed shortly before it
    expires, so concurrent exporters and the Langfuse client share a single
    valid token without each minting their own.
    """

    def __init__(
        self,
        auth_url: Optional[str],
        client_id: Optional[str],
        client_secret: Optional[str],
        *,
        insecure: bool = False,
        refresh_buffer: float = 30.0,
        timeout: float = 10.0,
        logger: Optional[logging.Logger] = None,
    ):
        self.auth_url = auth_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.insecure = insecure
        self.refresh_buffer = refresh_buffer
        self.timeout = timeout
        self._logger = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._expiry: float = 0.0

    @property
    def enabled(self) -> bool:
        return bool(self.auth_url and self.client_id and self.client_secret)

    @classmethod
    def from_config(
        cls, control_plane: Optional[dict], *, logger: Optional[logging.Logger] = None
    ) -> Optional["KeycloakTokenProvider"]:
        """Build a provider from a ``control_plane`` config block, or None if unconfigured."""
        if not control_plane:
            return None
        provider = cls(
            auth_url=control_plane.get("auth_url"),
            client_id=control_plane.get("client_id"),
            client_secret=control_plane.get("client_secret"),
            insecure=bool(control_plane.get("insecure", False)),
            logger=logger,
        )
        return provider if provider.enabled else None

    def token(self) -> Optional[str]:
        """Return a valid bearer token (cached), or None if unconfigured/unavailable."""
        if not self.enabled:
            return None
        with self._lock:
            if self._token and time.time() < self._expiry:
                return self._token
            return self._request_token()

    def _request_token(self) -> Optional[str]:
        try:
            resp = httpx.post(
                self.auth_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                verify=not self.insecure,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:
            self._logger.warning("Failed to fetch Keycloak token from %s: %s", self.auth_url, e)
            return None

        token = payload.get("access_token")
        if not token:
            self._logger.warning("Keycloak token response had no access_token")
            return None

        # Refresh ahead of the real expiry to avoid using a token mid-flight: a
        # fixed buffer for normal-lived tokens, but never before half the TTL so a
        # short-lived token isn't re-fetched on every single request.
        ttl = float(payload.get("expires_in", 300))
        self._token = token
        self._expiry = time.time() + max(ttl - self.refresh_buffer, ttl * 0.5)
        self._logger.debug("Obtained Keycloak access token (ttl=%ss)", ttl)
        return token


class _RequestsBearerAuth(requests.auth.AuthBase):
    """requests per-request auth that stamps a fresh Keycloak bearer token.

    The OTLP HTTP exporter freezes its headers into a ``requests.Session`` at
    construction, so a token placed there would never refresh. requests instead
    invokes ``session.auth`` on every request, so routing the token through here
    means each export re-reads the (auto-refreshing) token and a long-running
    process never sends an expired one.
    """

    def __init__(self, token_provider: KeycloakTokenProvider):
        self._token_provider = token_provider

    def __call__(self, request):
        token = self._token_provider.token()
        if token:
            request.headers["Authorization"] = f"Bearer {token}"
        return request


class _HttpxBearerAuth(httpx.Auth):
    """httpx per-request auth mirroring :class:`_RequestsBearerAuth` for the Langfuse client."""

    def __init__(self, token_provider: KeycloakTokenProvider):
        self._token_provider = token_provider

    def auth_flow(self, request):
        token = self._token_provider.token()
        if token:
            request.headers["Authorization"] = f"Bearer {token}"
        yield request


@dataclass
class OtelObservability:
    """Bootstraps OTLP log + trace export with optional Keycloak authentication.

    Construct directly for full control, or via :meth:`from_config` to derive
    settings from a service config dict plus the environment.
    """

    service_name: str
    service_version: str = "unknown-0"
    environment: str = "development"

    # OTLP endpoint resolution: an explicit per-signal endpoint wins, otherwise
    # ``host`` + the signal path is used.
    host: Optional[str] = None
    logs_endpoint: Optional[str] = None
    traces_endpoint: Optional[str] = None
    logs_path: str = DEFAULT_LOGS_PATH
    traces_path: str = DEFAULT_TRACES_PATH

    # Extra static headers in OTEL_EXPORTER_OTLP_HEADERS form ("k=v,k2=v2").
    extra_headers: Optional[str] = None
    org_id: str = "2"

    # Basic-auth fallback when Keycloak is not configured.
    fallback_public_key: Optional[str] = None
    fallback_secret_key: Optional[str] = None

    # Langfuse client credentials (project identity); transport auth still goes
    # through Keycloak when a token provider is present.
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None
    langfuse_host: Optional[str] = None

    token_provider: Optional[KeycloakTokenProvider] = None
    instrument_llama_index: bool = True
    logger: Optional[logging.Logger] = None

    def __post_init__(self):
        if self.logger is None:
            self.logger = logging.getLogger(__name__)
        self._tracer_provider: Optional[TracerProvider] = None
        self._logger_provider: Optional[LoggerProvider] = None

    @classmethod
    def from_config(
        cls,
        config_data: dict,
        service_name: str,
        service_version: str = "unknown-0",
        *,
        env: Optional[Dict[str, str]] = None,
        logger: Optional[logging.Logger] = None,
    ) -> "OtelObservability":
        """Build from a service config dict, with environment overrides.

        Reads ``control_plane`` (Keycloak) and ``observability.langfuse`` from
        ``config_data``; ``OTEL_*`` / ``LANGFUSE_*`` / ``GTS_ORG`` /
        ``DEPLOYMENT_ENVIRONMENT`` environment variables override or supplement.
        """
        import os

        env = env if env is not None else os.environ
        logger = logger or logging.getLogger(__name__)

        control_plane = config_data.get("control_plane") or {}
        token_provider = KeycloakTokenProvider.from_config(control_plane, logger=logger)

        langfuse_cfg = (config_data.get("observability", {}) or {}).get("langfuse") or {}
        public_key = langfuse_cfg.get("public_key") or env.get("LANGFUSE_PUBLIC_KEY")
        secret_key = langfuse_cfg.get("secret_key") or env.get("LANGFUSE_SECRET_KEY")
        langfuse_host = langfuse_cfg.get("host", control_plane.get("base_url")) or env.get("LANGFUSE_BASE_URL")

        host = (
            env.get("OTEL_EXPORTER_OTLP_ENDPOINT")
            or env.get("LANGFUSE_BASE_URL")
            or langfuse_host
        )

        return cls(
            service_name=service_name,
            service_version=service_version,
            environment=env.get("DEPLOYMENT_ENVIRONMENT", "development"),
            host=host,
            logs_endpoint=env.get("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT"),
            traces_endpoint=env.get("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT"),
            extra_headers=env.get("OTEL_EXPORTER_OTLP_HEADERS"),
            org_id=env.get("GTS_ORG", "2"),
            fallback_public_key=public_key,
            fallback_secret_key=secret_key,
            langfuse_public_key=public_key,
            langfuse_secret_key=secret_key,
            langfuse_host=langfuse_host,
            token_provider=token_provider,
            logger=logger,
        )

    # -- header / endpoint / exporter construction --------------------------------

    def build_headers(self) -> Dict[str, str]:
        """Static OTLP headers, including the initial Authorization.

        Precedence: an explicit Authorization in ``extra_headers`` > a Keycloak
        bearer token > Langfuse Basic Auth. When Keycloak is active the per-request
        auth hook refreshes this header on every export; the static value here is
        only the seed used at construction.
        """
        headers: Dict[str, str] = {}

        if self.extra_headers:
            for item in self.extra_headers.split(","):
                if "=" in item:
                    k, v = item.split("=", 1)
                    headers[k.strip()] = v.strip()

        if "Authorization" not in headers and self.token_provider and self.token_provider.enabled:
            token = self.token_provider.token()
            if token:
                headers["Authorization"] = f"Bearer {token}"

        if "Authorization" not in headers and self.fallback_public_key and self.fallback_secret_key:
            auth_b64 = base64.b64encode(
                f"{self.fallback_public_key}:{self.fallback_secret_key}".encode("utf-8")
            ).decode("utf-8")
            headers["Authorization"] = f"Bearer {auth_b64}"

        headers["x-org-id"] = self.org_id
        return headers

    def _resolve_endpoint(self, explicit: Optional[str], path: str) -> Optional[str]:
        if explicit:
            return explicit
        if self.host:
            return self.host if self.host.endswith(path) else self.host.rstrip("/") + path
        return None

    def _attach_dynamic_auth(self, exporter):
        """Refresh the Keycloak bearer token on every export for this exporter."""
        if (
            self.token_provider
            and self.token_provider.enabled
            and getattr(exporter, "_session", None) is not None
        ):
            exporter._session.auth = _RequestsBearerAuth(self.token_provider)
        return exporter

    def _exporter_kwargs(self, endpoint: Optional[str]) -> dict:
        kwargs: dict = {}
        if endpoint:
            kwargs["endpoint"] = endpoint
        headers = self.build_headers()
        if headers:
            kwargs["headers"] = headers
        return kwargs

    def make_span_exporter(self) -> OTLPSpanExporter:
        """An OTLP span exporter for the traces endpoint, Keycloak-authed if configured."""
        endpoint = self._resolve_endpoint(self.traces_endpoint, self.traces_path)
        return self._attach_dynamic_auth(OTLPSpanExporter(**self._exporter_kwargs(endpoint)))

    def make_log_exporter(self) -> OTLPLogExporter:
        """An OTLP log exporter for the logs endpoint, Keycloak-authed if configured."""
        endpoint = self._resolve_endpoint(self.logs_endpoint, self.logs_path)
        return self._attach_dynamic_auth(OTLPLogExporter(**self._exporter_kwargs(endpoint)))

    # -- lifecycle ----------------------------------------------------------------

    @property
    def tracer_provider(self) -> Optional[TracerProvider]:
        return self._tracer_provider

    def init(self):
        """Configure OTLP log + trace export and return a tracer for manual spans.

        Sets up a LoggerProvider and TracerProvider (both exporting over OTLP),
        attaches a LoggingHandler so stdlib logging records are exported, and
        (optionally) instruments LlamaIndex with the TracerProvider so its spans
        share the context the LoggingHandler reads for trace/log correlation.

        Returns the tracer to open a root span with, or None if exporter setup
        failed.
        """
        resource = Resource.create({
            "service.name": self.service_name,
            "service.version": self.service_version,
            "deployment.environment": self.environment,
        })

        logger_provider = LoggerProvider(resource=resource)
        set_logger_provider(logger_provider)
        self._logger_provider = logger_provider

        tracer_provider: Optional[TracerProvider] = None
        try:
            # Logs: bridge stdlib logging into the LoggerProvider via a LoggingHandler.
            logger_provider.add_log_record_processor(
                SimpleLogRecordProcessor(self.make_log_exporter())
            )
            atexit.register(logger_provider.shutdown)

            # Traces: a real TracerProvider so OpenInference emits recording spans.
            # Without this, spans are non-recording (invalid span context) and the
            # LoggingHandler cannot stamp trace_id/span_id onto exported log records.
            tracer_provider = TracerProvider(resource=resource)
            tracer_provider.add_span_processor(
                SimpleSpanProcessor(self.make_span_exporter())
            )
            atexit.register(tracer_provider.shutdown)
        except Exception as e:
            self.logger.warning("Failed to initialize OTLP exporters: %s", e)

        self._tracer_provider = tracer_provider

        # Pass our TracerProvider explicitly so OpenInference spans are recording
        # and share the context the LoggingHandler reads for trace correlation.
        if self.instrument_llama_index:
            self._instrument_llama_index(tracer_provider)
        # LoggingInstrumentor only injects trace/span IDs into log records for
        # correlation; the LoggingHandler is what actually exports logs.
        LoggingInstrumentor().instrument()
        logging.getLogger().addHandler(
            LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
        )

        return tracer_provider.get_tracer(self.service_name) if tracer_provider is not None else None

    def _instrument_llama_index(self, tracer_provider):
        try:
            from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
        except Exception as e:
            self.logger.warning("LlamaIndex instrumentation unavailable: %s", e)
            return
        LlamaIndexInstrumentor().instrument(tracer_provider=tracer_provider)

    def build_langfuse_client(self):
        """Construct (and register) the Langfuse client, authenticated like the exporters.

        With Keycloak configured, both the Langfuse trace exporter and its REST
        transport are routed through a refreshing bearer token instead of the
        static project keys. Without it, returns the default key-authenticated
        client. Returns None if Langfuse is unavailable or keys are missing.
        """
        try:
            from langfuse import Langfuse, get_client
        except Exception as e:
            self.logger.warning("Langfuse unavailable: %s", e)
            return None

        if not (self.langfuse_public_key and self.langfuse_secret_key):
            return None

        if not (self.token_provider and self.token_provider.enabled):
            return get_client()

        httpx_client = httpx.Client(
            timeout=_DEFAULT_HTTP_TIMEOUT,
            auth=_HttpxBearerAuth(self.token_provider),
            verify=not self.token_provider.insecure,
        )
        # span_exporter routes Langfuse's own span processor through our
        # Keycloak-authed exporter rather than one built from the project keys.
        return Langfuse(
            public_key=self.langfuse_public_key,
            secret_key=self.langfuse_secret_key,
            host=self.langfuse_host,
            httpx_client=httpx_client,
            span_exporter=self.make_span_exporter(),
        )
