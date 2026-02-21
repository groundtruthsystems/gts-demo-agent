import json
import os
from typing import Dict, Any

from pydantic import BaseModel


class Input(BaseModel):
    input_data: Dict[str, Any]

    def get(self, key, default=None):
        return self.input_data.get(key, default)


def load_input(_file):
    input_location = os.environ.get("INPUT_LOCATION", ".")
    if not input_location:
        raise EnvironmentError("INPUT_LOCATION environment variable not set.")

    input_file = os.path.join(input_location, _file)

    try:
        with open(input_file, 'r') as f:
            input_data = json.load(f)
        return Input(input_data=input_data)
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {input_file}")
    except json.JSONDecodeError:
        raise json.JSONDecodeError(f"Invalid JSON in input file: {input_file}")
