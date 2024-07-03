"""
title: Infomaniak Proxy Pipe
author: Shayano
author_url: https://github.com/Shayano/
funding_url: https://github.com/Shayano/infomaniak-openwebui-pipeline/functions/
version: 0.1.0

For this proxy pipeline to work properly, you need to change the maximum context value in the model's advanced params.
Change the value "Context Length" (num_ctx) for one of the followings values.

Set 32000 for mixtral
Set 23000 for mixtral8x22b
Set 8000 for llama3
"""


from pydantic import BaseModel, Field
from typing import Union, Generator, Iterator
import requests


class Pipe:
    class Valves(BaseModel):
        INFOMANIAK_API_KEY: str = Field(
            default="",
            description="API key for authenticating requests to the Infomaniak API.",
        )
        PRODUCT_ID: int = Field(
            default=0,
            description="Product ID for accessing the Infomaniak LLM API.",
        )
        NAME_PREFIX: str = Field(
            default="Infomaniak ",
            description="Prefix to be added before model names.",
        )
        pass

    def __init__(self):
        self.type = "manifold"
        self.valves = self.Valves()
        self.model_map = {}
        pass

    def pipes(self):
        if self.valves.INFOMANIAK_API_KEY:
            try:
                headers = {
                    "Authorization": f"Bearer {self.valves.INFOMANIAK_API_KEY}",
                    "Content-Type": "application/json",
                }
                url = "https://api.infomaniak.com/1/ai/models"

                r = requests.get(url, headers=headers)
                r.raise_for_status()
                models = r.json()

                # Process and return models only of type 'llm'
                models_list = [
                    {
                        "id": model["id"],
                        "name": f'{self.valves.NAME_PREFIX}{model["name"]}',
                    }
                    for model in models["data"]
                    if model["type"] == "llm"
                ]

                # Create a map from id to real name
                self.model_map = {
                    model["id"]: model["name"]
                    for model in models["data"]
                    if model["type"] == "llm"
                }

                return models_list

            except Exception as e:
                print(f"Error: {e}")
                return [
                    {
                        "id": "error",
                        "name": "Could not fetch models, please update the API Key in the valves.",
                    },
                ]
        else:
            return [
                {
                    "id": "error",
                    "name": "API Key not provided.",
                },
            ]

    def pipe(self, body: dict, __user__: dict) -> Union[str, Generator, Iterator]:
        print(f"pipe:{__name__}")

        if not self.valves.INFOMANIAK_API_KEY:
            return "API Key not provided."

        headers = {
            "Authorization": f"Bearer {self.valves.INFOMANIAK_API_KEY}",
            "Content-Type": "application/json",
        }

        model_id_str = body.get("model", "").rsplit(".", 1)[-1]
        try:
            model_id = int(model_id_str)
        except ValueError:
            return f"Invalid model format provided: {body.get('model')}"

        model_real_name = self.model_map.get(model_id)
        if not model_real_name:
            return f"Invalid model id provided: {model_id}"

        url = f"https://api.infomaniak.com/1/ai/{self.valves.PRODUCT_ID}/openai/chat/completions"
        payload = {**body, "model": model_real_name}
        print("Payload for request:", payload)

        try:
            r = requests.post(
                url=url,
                json=payload,
                headers=headers,
                stream=True,
            )

            r.raise_for_status()

            if body.get("stream"):
                return r.iter_lines()
            else:
                return r.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return f"Error: {e}"
