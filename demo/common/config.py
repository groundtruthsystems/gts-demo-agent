import json
import os
from typing import Dict, Any

from pydantic import BaseModel


class Config(BaseModel):
    config_data: Dict[str, Any]

    def get(self, key, default=None):
        return self.config_data.get(key, default)

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