# infomaniak-openwebui-pipeline

### Overview

This project provides a pipeline to integrate Infomaniak's Cloud AI service with Open WebUI. It allows you to send chat messages to the Infomaniak AI API and receive responses seamlessly.

### Features

- **API Integration**: Utilizes Infomaniak Cloud AI API for chat completions.
- **Configuration Management**: Loads API keys and model settings from environment variables.
- **Async Lifecycle Methods**: Handles startup and shutdown processes.
- **Request Handling**: Sends user messages to the Infomaniak API and processes responses.

### Code Explanation

The provided code defines a `Pipeline` class with the following key components:

1. **Valves Class**:
   - Stores configuration parameters (`INFOMANIAK_API_KEY`, `PRODUCT_ID`, and `MODEL`) which are loaded from environment variables.

2. **Initialization**:
   - Initializes the `Pipeline` with default values for the API key, product ID, and model name.

3. **Lifecycle Methods**:
   - `on_startup`: Placeholder for startup actions.
   - `on_shutdown`: Placeholder for shutdown actions.

4. **pipe Method**:
   - Handles the main logic of sending a chat message to the Infomaniak API.
   - Constructs the request payload and headers.
   - Sends the request to the Infomaniak API and returns the response.

### How to Use

1. **Set Environment Variables**:
   - `INFOMANIAK_API_KEY`: Your Infomaniak API key.
   - `PRODUCT_ID`: The product ID for the Infomaniak AI service.
   - `MODEL`: The model name to use (e.g., "mixtral", "mixtral8x22b", or "llama3").

2. **Run the Pipeline**:
   - Ensure your environment variables are set.
   - Import you code into the pipeline in Open Webui.
