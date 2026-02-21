import json
from pathlib import Path
from pydantic import BaseModel

def read_text_from_file(file: Path) -> str:
    try:
        with open(file, 'r') as f:
            input_data = f.read()
        return input_data
    except FileNotFoundError:
        raise FileNotFoundError(f"Input file not found: {file}")

def write_json_to_file(item: BaseModel, file: Path):
    try:
        with open(file, 'w') as f:
            json_data = item.model_dump(mode='json', exclude_unset=True)
            json.dump(json_data, f)
    except IOError:
        raise IOError(f"Could not write file: {str(file)}")