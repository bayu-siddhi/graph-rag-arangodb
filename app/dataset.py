import os
import re
import json
import tqdm
import sentence_transformers

from app import utils


class Dataset:
    
    def __init__(
        self, dir_path: str
    ) -> None:
        self.dir_path = dir_path

    
    def is_empty(
        self
    ) -> bool:
        json_files = [file for file in os.listdir(self.dir_path) if file.endswith(".json")]
        return not bool(json_files)


    def load_dataset(
        self
    ) -> dict[str, list[dict]]:
        json_data = {}
        json_files = sorted(
            [file for file in os.listdir(self.dir_path) if file.endswith(".json")],
            reverse=True
        )
        
        for json_file in json_files:
            with open(os.path.join(self.dir_path, json_file), "r", encoding="utf-8") as file:
                json_data[os.path.splitext(json_file)[0]] = json.load(file)
        
        return json_data


    def prepare_dataset(
        self,
        data: list[dict],
        embedding_model: str,
        device: str,
        verbose: bool = True
    ) -> None:
        embedding_model = sentence_transformers.SentenceTransformer(
            model_name_or_path=embedding_model, device=device
        )
        
        result = {
        # Node
            "node_Regulation": [],
            "node_Consideration": [],
            "node_Observation": [],
            "node_Article": [],
            "node_Definition": [],
        # Relationship
            "edge_reg_AMENDED_BY": [],
            "edge_HAS_CONSIDERATION": [],
            "edge_HAS_OBSERVATION": [],
            "edge_HAS_DEFINITION": [],
            "edge_HAS_ARTICLE": [],
            "edge_NEXT_ARTICLE": [],
            "edge_REFER_TO": [],
            "edge_art_AMENDED_BY": [],
        }

        edge_next_article_1 = []
        edge_nest_article_2 = []

        for regulation in tqdm.tqdm(iterable=data, desc="Transform regulation data", disable=not verbose):
            result["node_Regulation"].append({
                "id": int(regulation["id"]),
                "title": regulation["title"],
                "type": regulation["short_type"],
                "number": int(regulation["number"]),
                "year": int(regulation["year"]),
                "is_amendment": bool(int(regulation["amendment"])),
                "institution": regulation["institution"],
                "issue_place": regulation["issue_place"],
                "issue_date": regulation["issue_date"] if regulation["issue_date"] else None,
                "effective_date": regulation["effective_date"] if regulation["effective_date"] else None,
                "subjects": regulation["subjects"],
                "reference_url": regulation["url"],
                "download_url": regulation["download_link"],
                "download_name": regulation["download_name"]
            })

            for amended_regulation in regulation["status"]["amend"]:
                if re.search(r"peraturan\.bpk\.go\.id", amended_regulation, re.IGNORECASE) is None:
                    result["edge_reg_AMENDED_BY"].append({
                        "from_type": "Regulation",
                        "from": int(amended_regulation),
                        "to_type": "Regulation",
                        "to": int(regulation["id"]),
                        "amendment_number": int(regulation["amendment"])
                    })

            for key, content in regulation["content"].items():
                if key == "considering":
                    result["node_Consideration"].append({
                        "id": int(content["id"]),
                        "text": content["text"],
                        "embedding": embedding_model.encode(content["text"]).tolist()
                    })

                    result["edge_HAS_CONSIDERATION"].append({
                        "from_type": "Regulation",
                        "from": int(regulation["id"]),
                        "to_type": "Consideration",
                        "to": int(content["id"])
                    })

                elif key == "observing":
                    result["node_Observation"].append({
                        "id": int(content["id"]),
                        "text": content["text"],
                        "embedding": embedding_model.encode(content["text"]).tolist()

                    })

                    result["edge_HAS_OBSERVATION"].append({
                        "from_type": "Regulation",
                        "from": int(regulation["id"]),
                        "to_type": "Observation",
                        "to": int(content["id"])
                    })

                elif key == "articles":
                    for article in content.values():
                        text = (
                            f"{regulation['title']}, "
                            f"{(article['chapter_about'] or '') + ', ' if article['chapter_about'] else ''}"
                            f"{(article['part_about'] or '') + ', ' if article['part_about'] else ''}"
                            f"{(article['paragraph_about'] or '') + ', ' if article['paragraph_about'] else ''}"
                            f"Pasal {article['article_number']}:\n"
                            f"{article['text']}".strip()
                        )

                        result["node_Article"].append({
                            "id": int(article["id"]),
                            "number": article["article_number"],
                            "chapter": article["chapter_number"] if article["chapter_number"] else None,
                            "part": article["part_number"] if article["part_number"] else None,
                            "paragraph": article["paragraph_number"] if article["paragraph_number"] else None,
                            "text": text,
                            "embedding": embedding_model.encode(text).tolist()
                        })

                        result["edge_HAS_ARTICLE"].append({
                            "from_type": "Regulation",
                            "from": int(regulation["id"]),
                            "to_type": "Article",
                            "to": int(article["id"])
                        })

                        if article["previous_article"]:
                            edge_next_article_1.append((
                                int(article["previous_article"]),
                                int(article["id"]),
                                int(regulation["amendment"])
                            ))

                        if article["next_article"]:
                            edge_nest_article_2.append((
                                int(article["id"]),
                                int(article["next_article"]),
                                int(regulation["amendment"])
                            ))

                        if article["references"]:
                            for reference_article_id in article["references"]:
                                result["edge_REFER_TO"].append({
                                    "from_type": "Article",
                                    "from": int(article["id"]),
                                    "to_type": "Article",
                                    "to": int(reference_article_id)
                                })

                        if article["amend"]:
                            for amended_article_id in article["amend"]:
                                result["edge_art_AMENDED_BY"].append({
                                    "from_type": "Article",
                                    "from": int(amended_article_id),
                                    "to_type": "Article",
                                    "to": int(article["id"])
                                })

                else:
                    for definition in content:
                        text = (
                            f"{regulation['title']}, "
                            f"Definisi {definition['name']}:\n"
                            f"{definition['definition']}".strip()
                        )

                        result["node_Definition"].append({
                            "id": int(definition["id"]),
                            "name": definition["name"],
                            "text": text,
                            "embedding": embedding_model.encode(text).tolist()
                        })

                        result["edge_HAS_DEFINITION"].append({
                            "from_type": "Regulation",
                            "from": int(regulation["id"]),
                            "to_type": "Definition",
                            "to": int(definition["id"])
                        })

        for edge in sorted(set(edge_next_article_1 + edge_nest_article_2)):
            result["edge_NEXT_ARTICLE"].append({
                "from_type": "Article",
                "from": edge[0],
                "to_type": "Article",
                "to": edge[1],
                "amendment_number": edge[2]
            })

        for key, value in tqdm.tqdm(iterable=result.items(), desc="Save transformed data to JSON", disable=not verbose):
            utils.list_of_dict_to_json(data=value, output_path=os.path.join(self.dir_path, f"{key}.json"))
