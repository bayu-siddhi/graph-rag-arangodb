import os
import PIL
import json
import typing 
import gradio as gr

from app import dataset
from app import database
from langchain_community import graphs


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


def load_image(
    filepath: str
) -> PIL.ImageFile.ImageFile|None:
    try:
        image = PIL.Image.open(filepath)
        return image
    except FileNotFoundError:
        print(f"Error: Image file not found at {filepath}")
        return None


def check_database_status(
    dataset_obj: dataset.Dataset,
    database_obj: database.Database
) -> tuple[bool, bool]:
    is_dataset_empty = dataset_obj.is_empty()
    if not is_dataset_empty:
        dataset = dataset_obj.load_dataset()
        is_graph_empty = database_obj.is_empty(dataset=dataset)
    else:
        is_graph_empty = True
    return is_dataset_empty, is_graph_empty


def refresh_status(
    dataset_obj: dataset.Dataset,
    database_obj: database.Database
) -> tuple[dict[str, bool], dict[str, bool]]:
    is_dataset_empty, is_graph_empty = check_database_status(
        dataset_obj=dataset_obj, database_obj=database_obj
    )

    return (
        gr.update(visible=(is_dataset_empty or is_graph_empty)),
        gr.update(visible=(not is_dataset_empty and not is_graph_empty))
    )


def refresh_database_schema(
    arango_graph: graphs.ArangoGraph
) -> None:
    new_schema = arango_graph.generate_schema()
    new_schema = exclude_keys_from_data(new_schema, excluded_keys=["embedding"])
    arango_graph.set_schema(new_schema)


def prepare_and_load_database_with_status(
    dataset_obj: dataset.Dataset,
    database_obj: database.Database,
    arango_graph: graphs.ArangoGraph,
    device: str
) -> typing.Generator:
    yield "<center><h3>⏳ Preparing and loading database... Please wait</h3></center>", \
        gr.update(), \
        gr.update()    

    json_raw_input = os.path.join("data", "raw", "raw.json")
    with open(json_raw_input) as file:
        json_data = json.load(file)

    dataset_obj.prepare_dataset(
        data=json_data,
        embedding_model=os.environ["EMBEDDING_MODEL"],
        device=device,
        verbose=True
    )

    dataset = dataset_obj.load_dataset()

    database_obj.load_dataset_to_arangodb(dataset=dataset)

    refresh_database_schema(arango_graph=arango_graph)

    yield "<center><h3>✅ Database preparation complete! You can now use the chatbot</h3></center>", \
        gr.update(visible=False), \
        gr.update(visible=True)
    