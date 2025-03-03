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
____
Based on work of owndev: https://github.com/owndev/Open-WebUI-Functions
"""
from typing import List, Union, Generator, Iterator, Optional, Dict, Any
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask
from open_webui.env import AIOHTTP_CLIENT_TIMEOUT, SRC_LOG_LEVELS
import aiohttp
import json
import os
import logging
import traceback


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
    # Environment variables and configuration
    class Valves(BaseModel):
        # API key for Infomaniak
        INFOMANIAK_API_KEY: str = Field(
            default=os.getenv("INFOMANIAK_API_KEY", ""),
            description="API key for authenticating requests to the Infomaniak API.",
        )

        # Product ID for accessing the Infomaniak LLM API
        PRODUCT_ID: int = Field(
            default=int(os.getenv("INFOMANIAK_PRODUCT_ID", "0")),
            description="Product ID for accessing the Infomaniak LLM API.",
        )

        # Prefix to be added before model names
        NAME_PREFIX: str = Field(
            default=os.getenv("INFOMANIAK_NAME_PREFIX", "Infomaniak "),
            description="Prefix to be added before model names.",
        )

        # Base API URL for Infomaniak
        INFOMANIAK_BASE_URL: str = Field(
            default=os.getenv("INFOMANIAK_BASE_URL", "https://api.infomaniak.com/1/ai"),
            description="Base URL for Infomaniak API.",
        )

    def __init__(self):
        try:
            self.valves = self.Valves()
            self.name: str = "Infomaniak Manifold"
            self.type: str = "manifold"
            self.model_map = {}  # Initialize as empty dict

            # Configure logging with more details
            self.log = logging.getLogger("infomaniak.pipe")
            self.log.setLevel(SRC_LOG_LEVELS.get("OPENAI", logging.INFO))

            # Add a console handler if not already present
            if not self.log.handlers:
                console_handler = logging.StreamHandler()
                console_handler.setLevel(logging.DEBUG)
                formatter = logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                )
                console_handler.setFormatter(formatter)
                self.log.addHandler(console_handler)

            self.log.info("Initializing Infomaniak Manifold Pipeline")
            self.log.debug(f"Initial model_map type: {type(self.model_map)}")

        except Exception as e:
            print(f"ERROR IN INIT: {str(e)}")
            print(traceback.format_exc())
            # Still initialize basic attributes even if error occurs
            self.valves = self.Valves()
            self.name = "Infomaniak Manifold"
            self.type = "manifold"
            self.model_map = {}
            self.log = logging.getLogger("infomaniak.pipe")

    def validate_environment(self) -> None:
        """
        Validates that required environment variables are set.

        Raises:
            ValueError: If required environment variables are not set.
        """
        try:
            if not self.valves.INFOMANIAK_API_KEY:
                raise ValueError("INFOMANIAK_API_KEY is not set!")
            if self.valves.PRODUCT_ID <= 0:
                raise ValueError("INFOMANIAK_PRODUCT_ID must be a positive integer!")
        except Exception as e:
            self.log.error(f"Environment validation error: {str(e)}")
            self.log.error(traceback.format_exc())
            raise

    def get_headers(self) -> Dict[str, str]:
        """
        Constructs the headers for the API request.

        Returns:
            Dictionary containing the required headers for the API request.
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.valves.INFOMANIAK_API_KEY}",
                "Content-Type": "application/json",
            }
            self.log.debug(f"Headers created: {headers.keys()}")
            return headers
        except Exception as e:
            self.log.error(f"Error creating headers: {str(e)}")
            self.log.error(traceback.format_exc())
            raise

    def validate_body(self, body: Dict[str, Any]) -> None:
        """
        Validates the request body to ensure required fields are present.

        Args:
            body: The request body to validate

        Raises:
            ValueError: If required fields are missing or invalid.
        """
        try:
            if not isinstance(body, dict):
                raise ValueError(f"Body must be a dictionary, got {type(body)}")

            if "messages" not in body:
                raise ValueError("The 'messages' field is required.")

            if not isinstance(body["messages"], list):
                raise ValueError(
                    f"The 'messages' field must be a list, got {type(body['messages'])}"
                )

            if "model" not in body:
                raise ValueError("The 'model' field is required.")

            if not body["model"]:
                raise ValueError("Model cannot be empty.")

            self.log.debug("Request body validation passed")

        except Exception as e:
            self.log.error(f"Body validation error: {str(e)}")
            self.log.error(traceback.format_exc())
            raise

    async def fetch_models(self) -> List[Dict[str, str]]:
        """
        Fetches available LLM models from Infomaniak API asynchronously.

        Returns:
            List of dictionaries containing model id and name.
        """
        self.log.info("Fetching models from Infomaniak API")

        session = None
        try:
            session = aiohttp.ClientSession(
                trust_env=True,
                timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
            )

            # Get headers for the request
            try:
                headers = self.get_headers()
            except Exception as e:
                self.log.error(f"Error getting headers: {str(e)}")
                return [{"id": "error", "name": f"Could not create headers: {str(e)}"}]

            # Form the URL for models
            try:
                url = f"{self.valves.INFOMANIAK_BASE_URL}/models"
                self.log.debug(f"Fetching models from URL: {url}")
            except Exception as e:
                self.log.error(f"Error forming URL: {str(e)}")
                return [{"id": "error", "name": f"Could not form URL: {str(e)}"}]

            # Make the request
            try:
                self.log.debug("Making GET request to fetch models")
                response = await session.get(url, headers=headers)
                response.raise_for_status()

                # Parse the response
                response_text = await response.text()
                self.log.debug(f"Response received, length: {len(response_text)}")
                self.log.debug(
                    f"Response content: {response_text[:500]}..."
                )  # Log first 500 chars
                models_data = json.loads(response_text)

                # Debug the response structure
                self.log.debug(
                    f"Models data keys: {models_data.keys() if isinstance(models_data, dict) else 'not a dict'}"
                )

                if not isinstance(models_data, dict) or "data" not in models_data:
                    self.log.error(
                        f"Unexpected response structure: {type(models_data)}"
                    )
                    self.log.error(f"Response content: {response_text[:1000]}...")
                    return [{"id": "error", "name": "Unexpected response structure"}]

                if not isinstance(models_data["data"], list):
                    self.log.error(
                        f"models_data['data'] is not a list: {type(models_data['data'])}"
                    )
                    return [{"id": "error", "name": "Models data is not a list"}]

            except Exception as e:
                self.log.error(f"Error making request or parsing response: {str(e)}")
                self.log.error(traceback.format_exc())
                return [{"id": "error", "name": f"Request or parsing error: {str(e)}"}]

            # Process models data
            models_list = []
            self.model_map = {}  # Reset model map

            try:
                self.log.debug(f"Processing {len(models_data['data'])} models")

                for idx, model in enumerate(models_data["data"]):
                    try:
                        # Debug model structure
                        model_keys = (
                            model.keys() if isinstance(model, dict) else "not a dict"
                        )
                        self.log.debug(f"Model {idx} keys: {model_keys}")

                        if not isinstance(model, dict):
                            self.log.warning(
                                f"Model {idx} is not a dictionary, skipping"
                            )
                            continue

                        if "type" not in model:
                            self.log.warning(f"Model {idx} has no 'type' key, skipping")
                            continue

                        if "id" not in model:
                            self.log.warning(f"Model {idx} has no 'id' key, skipping")
                            continue

                        if "name" not in model:
                            self.log.warning(f"Model {idx} has no 'name' key, skipping")
                            continue

                        # Only process LLM models
                        if model["type"] == "llm":
                            self.log.debug(
                                f"Processing LLM model: {model['id']} - {model['name']}"
                            )

                            # Handle model ID conversion
                            try:
                                # Check the type of model ID
                                model_id_type = type(model["id"])
                                model_id_value = model["id"]
                                self.log.debug(
                                    f"Model ID type: {model_id_type}, value: {model_id_value}"
                                )

                                # Store model ID as both integer and string in model_map
                                if isinstance(model_id_value, str):
                                    try:
                                        model_id_int = int(model_id_value)
                                        # Store both string and int versions
                                        model_id_for_list = str(model_id_value)
                                        self.log.debug(
                                            f"Converted string ID '{model_id_value}' to int: {model_id_int}"
                                        )
                                    except ValueError:
                                        # If can't convert to int, just use the string
                                        model_id_int = None
                                        model_id_for_list = model_id_value
                                        self.log.debug(
                                            f"Could not convert ID to int, using string: {model_id_value}"
                                        )
                                else:
                                    model_id_int = model_id_value
                                    model_id_for_list = str(model_id_value)
                                    self.log.debug(
                                        f"Using original ID: {model_id_value}"
                                    )

                            except Exception as e:
                                self.log.warning(f"Error processing model ID: {str(e)}")
                                continue

                            # Add to models list
                            try:
                                models_list.append(
                                    {
                                        "id": model_id_for_list,
                                        "name": f"{self.valves.NAME_PREFIX}{model['name']}",
                                    }
                                )
                                self.log.debug(
                                    f"Added model to list: {model_id_for_list}"
                                )
                            except Exception as e:
                                self.log.warning(
                                    f"Error adding model to list: {str(e)}"
                                )
                                continue

                            # Add to model map dictionary using both string and int keys if possible
                            try:
                                # Always add with string key
                                self.log.debug(
                                    f"Adding to model_map with string key: {model_id_for_list}"
                                )
                                self.model_map[model_id_for_list] = model["name"]

                                # Also add with int key if available
                                if model_id_int is not None:
                                    self.log.debug(
                                        f"Adding to model_map with int key: {model_id_int}"
                                    )
                                    self.model_map[model_id_int] = model["name"]

                            except Exception as e:
                                self.log.error(f"Error adding to model_map: {str(e)}")
                                self.log.error(traceback.format_exc())
                                continue

                    except Exception as e:
                        self.log.warning(f"Error processing model {idx}: {str(e)}")
                        continue

                # Check results
                self.log.debug(f"model_map final size: {len(self.model_map)}")
                self.log.debug(f"model_map keys: {list(self.model_map.keys())}")
                self.log.debug(f"models_list length: {len(models_list)}")

                if len(models_list) == 0:
                    return [{"id": "error", "name": "No valid LLM models found"}]

                return models_list

            except Exception as e:
                self.log.error(f"Error processing models data: {str(e)}")
                self.log.error(traceback.format_exc())
                return [{"id": "error", "name": f"Error processing models: {str(e)}"}]

        except Exception as e:
            self.log.error(f"Error fetching models: {str(e)}")
            self.log.error(traceback.format_exc())
            return [{"id": "error", "name": f"Could not fetch models: {str(e)}"}]

        finally:
            if session:
                try:
                    await session.close()
                    self.log.debug("Session closed in fetch_models")
                except Exception as e:
                    self.log.warning(f"Error closing session: {str(e)}")

    async def pipes(self) -> List[Dict[str, str]]:
        """
        Returns a list of available models.

        Returns:
            List of dictionaries containing model id and name.
        """
        try:
            self.log.info("pipes() method called")

            try:
                self.validate_environment()
                self.log.debug("Environment validation passed")
            except ValueError as e:
                self.log.error(f"Environment validation error: {e}")
                return [{"id": "error", "name": str(e)}]

            try:
                models = await self.fetch_models()
                self.log.debug(f"fetch_models returned {len(models)} models")
                return models
            except Exception as e:
                self.log.error(f"Error in fetch_models: {str(e)}")
                self.log.error(traceback.format_exc())
                return [{"id": "error", "name": f"Error fetching models: {str(e)}"}]

        except Exception as e:
            self.log.error(f"Unhandled error in pipes: {str(e)}")
            self.log.error(traceback.format_exc())
            return [{"id": "error", "name": f"Unhandled error: {str(e)}"}]

    async def pipe(
        self, body: Dict[str, Any], __user__: Optional[Dict[str, Any]] = None
    ) -> Union[str, Generator, Iterator, Dict[str, Any], StreamingResponse]:
        """
        Main method for sending requests to the Infomaniak API.

        Args:
            body: The request body containing messages and other parameters
            __user__: Optional user context information

        Returns:
            Response from Infomaniak API, which could be a string, dictionary or streaming response
        """
        self.log.info("Processing request to Infomaniak API")
        self.log.debug(f"Request body: {body}")

        try:
            # Validate environment
            try:
                self.validate_environment()
                self.log.debug("Environment validation passed")
            except ValueError as e:
                return f"Environment validation error: {str(e)}"

            # Validate request body
            try:
                self.validate_body(body)
                self.log.debug("Request body validation passed")
            except ValueError as e:
                return f"Request validation error: {str(e)}"

            # Get model ID from the request
            try:
                model_identifier = body.get("model", "")
                self.log.debug(f"Original model identifier: {model_identifier}")

                # Try to extract the model ID from the end of the string
                if "." in model_identifier:
                    model_id_str = model_identifier.rsplit(".", 1)[-1]
                    self.log.debug(f"Extracted model_id_str: {model_id_str}")
                else:
                    model_id_str = model_identifier
                    self.log.debug(f"Using full model_id_str: {model_id_str}")

                # Try both string and integer lookups
                model_id_str_for_lookup = model_id_str

                # Try to convert to integer for lookup if possible
                try:
                    model_id_int = int(model_id_str)
                    self.log.debug(f"Also have integer model_id: {model_id_int}")
                except ValueError:
                    model_id_int = None
                    self.log.debug("Could not convert model_id to integer")

            except Exception as e:
                self.log.error(f"Error extracting model ID: {str(e)}")
                self.log.error(traceback.format_exc())
                return f"Error extracting model ID: {str(e)}"

            # Get real model name from the ID
            try:
                self.log.debug(f"model_map type: {type(self.model_map)}")
                self.log.debug(f"model_map keys: {list(self.model_map.keys())}")

                # Try lookup with both string and int versions
                model_real_name = None

                # Check string version first
                if model_id_str_for_lookup in self.model_map:
                    self.log.debug(
                        f"Found model using string key: {model_id_str_for_lookup}"
                    )
                    model_real_name = self.model_map[model_id_str_for_lookup]
                # Then check int version if available
                elif model_id_int is not None and model_id_int in self.model_map:
                    self.log.debug(f"Found model using int key: {model_id_int}")
                    model_real_name = self.model_map[model_id_int]
                else:
                    self.log.debug(
                        f"Model not found with either string key '{model_id_str_for_lookup}' or int key {model_id_int}"
                    )

                # If not found, try to fetch models
                if not model_real_name:
                    self.log.debug("Model not found, attempting to fetch models")
                    self.log.debug(f"Current model_map contents: {self.model_map}")

                    # Force a refresh of the models
                    await self.fetch_models()
                    self.log.debug(
                        f"After fetch, model_map has {len(self.model_map)} items: {self.model_map}"
                    )

                    # Try lookup again with both versions
                    if model_id_str_for_lookup in self.model_map:
                        model_real_name = self.model_map[model_id_str_for_lookup]
                        self.log.debug(
                            f"Found model using string key after refresh: {model_id_str_for_lookup}"
                        )
                    elif model_id_int is not None and model_id_int in self.model_map:
                        model_real_name = self.model_map[model_id_int]
                        self.log.debug(
                            f"Found model using int key after refresh: {model_id_int}"
                        )

                if not model_real_name:
                    self.log.error(
                        f"Model not found after refresh. Available keys: {list(self.model_map.keys())}"
                    )
                    self.log.error(
                        f"Looking for model with string key: {model_id_str_for_lookup} or int key: {model_id_int}"
                    )
                    return f"Invalid model id: {model_identifier} - Model not found in available models. Available models: {list(self.model_map.keys())}"

                self.log.debug(f"Found model_real_name: {model_real_name}")

            except Exception as e:
                self.log.error(f"Error looking up model name: {str(e)}")
                self.log.error(traceback.format_exc())
                return f"Error looking up model name: {str(e)}"

            # Filter allowed parameters
            try:
                allowed_params = {
                    "model",
                    "messages",
                    "frequency_penalty",
                    "max_tokens",
                    "presence_penalty",
                    "response_format",
                    "seed",
                    "stop",
                    "stream",
                    "temperature",
                    "tool_choice",
                    "tools",
                    "top_p",
                }
                filtered_body = {k: v for k, v in body.items() if k in allowed_params}
                self.log.debug(f"Filtered body keys: {filtered_body.keys()}")

                # Replace model ID with real model name
                filtered_body["model"] = model_real_name
                self.log.debug(f"Set model in request to: {model_real_name}")

            except Exception as e:
                self.log.error(f"Error filtering parameters: {str(e)}")
                self.log.error(traceback.format_exc())
                return f"Error filtering parameters: {str(e)}"

            # Convert the modified body to JSON
            try:
                payload = json.dumps(filtered_body)
                self.log.debug(f"Created JSON payload, length: {len(payload)}")
                self.log.debug(f"Payload first 500 chars: {payload[:500]}...")
            except Exception as e:
                self.log.error(f"Error creating JSON payload: {str(e)}")
                self.log.error(traceback.format_exc())
                return f"Error creating JSON payload: {str(e)}"

            # Create URL for the API request
            try:
                url = f"{self.valves.INFOMANIAK_BASE_URL}/{self.valves.PRODUCT_ID}/openai/chat/completions"
                self.log.debug(f"Request URL: {url}")
            except Exception as e:
                self.log.error(f"Error creating URL: {str(e)}")
                self.log.error(traceback.format_exc())
                return f"Error creating URL: {str(e)}"

            # Make the request to the API
            request = None
            session = None
            streaming = False
            response = None

            try:
                self.log.debug("Creating client session")
                session = aiohttp.ClientSession(
                    trust_env=True,
                    timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
                )

                self.log.debug("Getting headers for request")
                headers = self.get_headers()

                self.log.debug(f"Making POST request to {url}")
                request = await session.request(
                    method="POST",
                    url=url,
                    data=payload,
                    headers=headers,
                )

                self.log.debug(f"Request status: {request.status}")

                # Check if response is SSE
                content_type = request.headers.get("Content-Type", "")
                self.log.debug(f"Response Content-Type: {content_type}")

                if "text/event-stream" in content_type:
                    self.log.info("Streaming response detected")
                    streaming = True
                    return StreamingResponse(
                        request.content,
                        status_code=request.status,
                        headers=dict(request.headers),
                        background=BackgroundTask(
                            cleanup_response, response=request, session=session
                        ),
                    )
                else:
                    self.log.debug("Non-streaming response detected")
                    try:
                        response_text = await request.text()
                        self.log.debug(f"Response text length: {len(response_text)}")
                        self.log.debug(f"Response text: {response_text}")

                        try:
                            response = json.loads(response_text)
                            self.log.debug("Successfully parsed JSON response")
                            self.log.debug(f"Response JSON: {response}")
                        except Exception as e:
                            self.log.error(f"Error parsing JSON response: {e}")
                            self.log.debug(f"Raw response: {response_text[:500]}...")
                            response = response_text

                        request.raise_for_status()
                        self.log.info("Successfully processed non-streaming request")
                        return response

                    except aiohttp.ClientResponseError as e:
                        self.log.error(f"HTTP error: {e.status} - {e.message}")
                        detail = f"HTTP error {e.status}: {e.message}"
                        if isinstance(response, dict) and "error" in response:
                            detail = (
                                f"{response['error'].get('message', 'Unknown error')}"
                            )
                        return f"Error: {detail}"
                    except Exception as e:
                        self.log.error(f"Error processing response: {e}")
                        self.log.error(traceback.format_exc())
                        raise

            except Exception as e:
                self.log.exception(f"Error in Infomaniak API request: {e}")
                self.log.error(traceback.format_exc())

                detail = f"Exception: {str(e)}"
                if isinstance(response, dict):
                    if "error" in response:
                        detail = f"{response['error'].get('message', str(response['error']))}"
                elif isinstance(response, str):
                    detail = response

                return f"Error: {detail}"

            finally:
                if not streaming:
                    if request:
                        try:
                            request.close()
                            self.log.debug("Request closed")
                        except Exception as e:
                            self.log.warning(f"Error closing request: {str(e)}")

                    if session:
                        try:
                            await session.close()
                            self.log.debug("Session closed")
                        except Exception as e:
                            self.log.warning(f"Error closing session: {str(e)}")

        except Exception as e:
            self.log.error(f"Unhandled error in pipe: {str(e)}")
            self.log.error(traceback.format_exc())
            return f"Unhandled error: {str(e)}\n\nStack trace: {traceback.format_exc()}"
