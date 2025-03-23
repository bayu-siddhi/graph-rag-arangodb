import PIL
import json
import typing


def list_of_dict_to_json(
    data: list[dict], output_path: str
) -> None:
    if not output_path.endswith(".json"):
        output_path = f"{output_path}.json"

    with open(output_path, "w", encoding="utf-8") as output_file:
        json.dump(data, output_file, indent=4)


def exclude_keys_from_data(
    data: typing.Any, excluded_keys: list
) -> typing.Any:
    if isinstance(data, dict):
        new_data = {}
        for key, value in data.items():
            if key not in excluded_keys:
                new_data[key] = exclude_keys_from_data(value, excluded_keys)
        return new_data
    elif isinstance(data, list):
        new_data = []
        for item in data:
            new_data.append(exclude_keys_from_data(item, excluded_keys))
        return new_data
    else:
        return data


def load_image(filepath):
    try:
        image = PIL.Image.open(filepath)
        return image
    except FileNotFoundError:
        print(f"Error: Image file not found at {filepath}")
        return None
    