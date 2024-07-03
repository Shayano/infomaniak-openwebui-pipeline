# Infomaniak Open WebUI Pipeline

This project is a pipeline for interacting with the Infomaniak OpenAI API. It allows for managing API requests and responses using various models and configurations.

## Configuration

To use this pipeline, you need to set the following environment variables after importing the file into the Open WebUI pipeline section :

- `INFOMANIAK_API_KEY`: Your Infomaniak API key.
- `PRODUCT_ID`: The ID of the product associated with your API key.
- `MODEL`: The OpenAI model you wish to use (e.g., "mixtral", "mixtral8x22b", "llama3").

## Usage

This file is intended to be used as an entry point for integrating the Infomaniak OpenAI API into your projects. Modify the environment variable values as needed to configure the pipeline's behavior.

For this pipeline to work properly, you need to change the maximum context value in the model's advanced params.  
Change the value "Context Length" (num_ctx) for one of the followings values. 

Set 32000 for mixtral   
Set 23000 for mixtral8x22b  
Set 8000 for llama3  


## Update 03.07.2024
I have created a new script that is now available in the functions folder. This function makes it much easier to implement compared to using a pipeline.
With this function, there is no need to manually define the models. Simply add the function and set the API, Product ID, prefix and it will automatically fetch the required models for you.
The function is also available for download from the Open WebUI website at <https://openwebui.com/f/shayoo/infomaniak_proxy_pipe/>.

