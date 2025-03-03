"""
title: Infomaniak Manifold
author: Shayano
author_url: https://github.com/Shayano/
funding_url: https://github.com/open-webui
version: 0.2.0

For this proxy pipeline to work properly, you need to change the maximum context value in the model's advanced params.
Change the value "Context Length" (num_ctx) for one of the followings values.

Set 32000 for mixtral
Set 23000 for mixtral8x22b
Set 8000 for llama3
https://developer.infomaniak.com/docs/api/get/1/ai

Based on work of owndev: https://github.com/owndev/Open-WebUI-Functions
"""
from typing import List, Union, Generator, Iterator, Dict, Any, Optional
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
import aiohttp
import json
import os
import logging

# Helper functions
async def cleanup_response(
    response: Optional[aiohttp.ClientResponse],
    session: Optional[aiohttp.ClientSession],
) -> None:
    """
    Clean up the response and session objects.
    Args:
        response: The ClientResponse object to close
        session: The ClientSession object to close
    """
    if response:
        response.close()
    if session:
        await session.close()

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

    def __init__(self):
        self.valves = self.Valves()
        self.model_map = {}

    def validate_environment(self) -> None:
        """
        Validates that required environment variables are set.
        Raises:
            ValueError: If required environment variables are not set.
        """
        if not self.valves.INFOMANIAK_API_KEY:
            raise ValueError("INFOMANIAK_API_KEY is not set!")

    def get_headers(self) -> Dict[str, str]:
        """
        Constructs the headers for the API request.
        Returns:
            Dictionary containing the required headers for the API request.
        """
        headers = {
            "Authorization": f"Bearer {self.valves.INFOMANIAK_API_KEY}",
            "Content-Type": "application/json"
        }
        return headers

    def validate_body(self, body: Dict[str, Any]) -> None:
        """
        Validates the request body to ensure required fields are present.
        Args:
            body: The request body to validate
        Raises:
            ValueError: If required fields are missing or invalid.
        """
        if "model" not in body or not isinstance(body["model"], str):
            raise ValueError("The 'model' field is required and must be a string.")

    async def pipes(self) -> List[Dict[str, str]]:
        self.validate_environment()
        headers = self.get_headers()
        url = "https://api.infomaniak.com/1/ai/models"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as r:
                    r.raise_for_status()
                    models = await r.json()
                    models_list = [
                        {
                            "id": model["id"],
                            "name": f'{self.valves.NAME_PREFIX}{model["name"]}',
                        }
                        for model in models["data"]
                        if model["type"] == "llm"
                    ]
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

    async def pipe(self, body: Dict[str, Any]) -> Union[str, Generator, Iterator, Dict[str, Any], StreamingResponse]:
        self.validate_environment()
        self.validate_body(body)
        headers = self.get_headers()
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

        session = None
        request = None
        response = None
        streaming = False
        try:
            session = aiohttp.ClientSession()
            request = await session.post(url, json=payload, headers=headers)
            request.raise_for_status()
            
            if body.get("stream"):
                streaming = True
                return StreamingResponse(
                    request.content,
                    status_code=request.status,
                    headers=dict(request.headers),
                    background=BackgroundTask(cleanup_response, response=request, session=session)
                )
            else:
                response = await request.json()
                return response
        except Exception as e:
            print(f"Request failed: {e}")
            detail = f"Exception: {str(e)}"
            if isinstance(response, dict) and "error" in response:
                detail = response['error'].get('message', response['error'])
            elif isinstance(response, str):
                detail = response
            return f"Error: {detail}"
        finally:
            if not streaming and session:
                if request:
                    request.close()
                await session.close()
            else:
                return r.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return f"Error: {e}"
