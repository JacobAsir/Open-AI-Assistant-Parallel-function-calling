import openai
from openai import OpenAI
import json
import requests
from serpapi import GoogleSearch
import time

import os
from dotenv import load_dotenv
load_dotenv()

os.environ["OPENAI_API_KEY"]  = os.getenv("OPENAI_API_KEY")
openai_api_key = os.environ["OPENAI_API_KEY"]

os.environ["Weather_API_KEY"]  = os.getenv("Weather_API_KEY")
wapi_key = os.environ["Weather_API_KEY"] 

os.environ["SERPER_API_KEY"]  = os.getenv("SERPER_API_KEY")
serpapi_key = os.environ["SERPER_API_KEY"]  


# Initialize the OpenAI client with API key
client = OpenAI(api_key= openai_api_key)

# Function for generating an image with DALL-E API
def dalle_api_generate_image(description):
    response = client.images.generate(
        model="dall-e-3",
        prompt=description,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    return response.data[0].url

# Function to get weather information
def get_weather(city, wapi_key = wapi_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={wapi_key}&units=metric"
    try:
        response = requests.get(url)
        response.raise_for_status()
        weather_data = response.json()
        return {
            "temperature": weather_data["main"]["temp"],
            "weather": weather_data["weather"][0]["description"],
            "city": weather_data["name"]
        }
    except requests.exceptions.HTTPError as err:
        return f"HTTP Error: {err}"
    except requests.exceptions.RequestException as err:
        return f"Error: {err}"
    except KeyError:
        return "Error: Problem parsing weather data."

# Function to get organic search results
def get_organic_results(query, api_key=serpapi_key):
    try:
        params = {
            "engine": "google",
            "num": "5",
            "q": query,
            "api_key": api_key
        }
        search = GoogleSearch(params)
        results = search.get_dict()
        organic_results = results.get("organic_results", [])
        urls = [result['link'] for result in organic_results]
        return urls
    except Exception as e:
        return f"Error performing search: {str(e)}"

def get_chat_response(user_input, model="gpt-4o"):
    try:
        # Create the chat completion request
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Help the USER with writing."},
                {"role": "user", "content": user_input}
            ]
        )

        # Extract and return the chat response text
        chat_response_text = completion.choices[0].message['content']
        return chat_response_text

    except Exception as e:
        # Handle any exceptions that occur during the API request
        return f"An error occurred: {str(e)}"
        
list_tools = [ {
            "type": "function",
            "function": {
                "name": "get_organic_results",
                "description": "Fetch news URLs based on a search query",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "api_key": {"type": "string", "description": "API key for SerpApi"}
                    },
                    "required": ["query"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "dalle_api_generate_image",
                "description": "Generate an image based on a description using DALL-E",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {"type": "string", "description": "Description for the image to generate"}
                    },
                    "required": ["description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Fetch weather information for a given city",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "city": {"type": "string", "description": "City name"},
                        "api_key": {"type": "string", "description": "API key for OpenWeatherMap"}
                    },
                    "required": ["city"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_chat_response",
                "description": "Provide chat responses to user queries",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "user_input": {"type": "string", "description": "User's query"},
                        "model": {"type": "string", "description": "GPT model to use"}
                    },
                    "required": ["user_input"]
                }
            }
        }
    ]


# Step 1: Create an Assistant with a specific name and tools
assistant = client.beta.assistants.create(
    name="ParallelFunction",
    instructions="You are an assistant capable of searching Google, generating images, providing weather information, and writing based on user queries.",
    model="gpt-4o",
    tools=list_tools
)

PINK = '\033[95m'
# ANSI escape code for cyan color
CYAN = '\033[96m'
# ANSI escape code for yellow color
YELLOW = '\033[93m'
# ANSI escape code to reset to default color
RESET_COLOR = '\033[0m'

# Step 2: Create a Thread
thread = client.beta.threads.create()

# Step 3: Add a Message to a Thread with user input
user_message_content = input(f"{PINK}Enter your message:{RESET_COLOR}")
message = client.beta.threads.messages.create(
    thread_id=thread.id,
    role="user",
    content=user_message_content
)

# Step 4: Run the Assistant
run = client.beta.threads.runs.create(
    thread_id=thread.id,
    assistant_id=assistant.id
    )

#print(run.model_dump_json(indent=4))

# Define a dispatch table
function_dispatch_table = {
    "get_organic_results": get_organic_results,
    "dalle_api_generate_image": dalle_api_generate_image,
    "get_weather": get_weather,
    "get_chat_response": get_chat_response
}

while True:
    # Wait for 5 seconds
    time.sleep(5)

    # Retrieve the run status
    run_status = client.beta.threads.runs.retrieve(
        thread_id=thread.id,
        run_id=run.id
    )

    # Comment out or remove the following line to prevent verbose output
    # print(run_status.model_dump_json(indent=4))

    # If run is completed, get messages
    if run_status.status == 'completed':
        messages = client.beta.threads.messages.list(
            thread_id=thread.id
        )

        # Loop through messages and print content based on role
        for msg in messages.data:
            role = msg.role
            content = msg.content[0].text.value
            # Only print the final message content
            if role == 'assistant':
                print(f"{YELLOW}{role.capitalize()}: {content}{RESET_COLOR}")
        break
    elif run_status.status == 'requires_action':
        print(f"{PINK}Requires action:{RESET_COLOR}")
        required_actions = run_status.required_action.submit_tool_outputs.model_dump()
        
        # Print the required action in the desired format
        tool_calls_output = {'tool_calls': [{'id': action['id'], 'function': {'arguments': action['function']['arguments'], 'name': action['function']['name']}, 'type': 'function'} for action in required_actions["tool_calls"]]}
        print(f"{PINK}{tool_calls_output}{RESET_COLOR}")

        tools_output = []

        for action in required_actions["tool_calls"]:
            func_name = action["function"]["name"]
            arguments = json.loads(action["function"]["arguments"])

            func = function_dispatch_table.get(func_name)
            if func:
                result = func(**arguments)
                # Ensure the output is a JSON string
                output = json.dumps(result) if not isinstance(result, str) else result
                tools_output.append({
                    "tool_call_id": action["id"],
                    "output": output
                })
            else:
                print(f"Function {func_name} not found")

        # Submit the tool outputs to Assistant API
        client.beta.threads.runs.submit_tool_outputs(
            thread_id=thread.id,
            run_id=run.id,
            tool_outputs=tools_output
        )

    else:
        print(f"{CYAN}Waiting for the Assistant to process...{RESET_COLOR}")
        time.sleep(5)
