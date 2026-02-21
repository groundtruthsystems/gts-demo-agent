import json
import os
from typing import Dict, Any

from pydantic import BaseModel


class Config(BaseModel):
    config_data: Dict[str, Any]

    def get(self, key, default=None):
        return self.config_data.get(key, default)

    def llm_config(self, vendor, model: str | None = None, purpose: str | None = None):
        configs = self.config_data.get("llms", {}).get(vendor, [])
        default = None
        for config in configs:
            if config.get("model", "") == model:
                return config
            if config.get("purpose", "") == purpose:
                return config
            if config.get("default", False):
                default = config

        return default

    def object_storage_bucket(self):
        return self.config_data.get("object_storage", {}).get("bucket")

    def object_storage(self):
        return self.config_data.get("object_storage", {}).get("vendor", "aws")

    def object_storage_aws(self):
        return self.config_data.get("object_storage", {}).get("aws")

    def object_storage_minio(self):
        return self.config_data.get("object_storage", {}).get("minio")

    def ontology_service_config(self):
        return self.config_data.get("gateways", {}).get("registry", {}).get("ontology")


def load_config():
    config_file = os.environ.get("CONFIG_LOCATION", "./config/default.json")

    try:
        with open(config_file, 'r') as f:
            config_data = json.load(f)
        return Config(config_data=config_data)
    except FileNotFoundError:
        raise FileNotFoundError(f"Configuration file not found: {config_file}")
    except json.JSONDecodeError:
        raise json.JSONDecodeError(f"Invalid JSON in configuration file: {config_file}")

if __name__ == '__main__':
    # Example usage
    os.environ["CONFIG_LOCATION"] = "/tmp"
    try:
        config = load_config()
        print(config.get("llm_provider"))
    except Exception as e:
        print(f"Error loading configuration: {e}")