import openai
import os
import requests
import re
import json
from colorama import Fore, Style, init
import datetime
import base64
from pydub import AudioSegment
from pydub.playback import play
import tkinter as tk
from PIL import Image, ImageTk
from flask import Flask, render_template, send_from_directory
from flask import jsonify, request


# Initialize colorama
init()

# Define a function to open a file and return its contents as a string
def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()

# Define a function to save content to a file
def save_file(filepath, content):
    with open(filepath, 'a', encoding='utf-8') as outfile:
        outfile.write(content)

# Set the OpenAI API keys by reading them from files
api_key = open_file('openaiapikey2.txt')

#sd api key
sd_api_key = open_file('sdapikey.txt')

# Set the Eleven Labs API key
elapikey = open_file('elabapikey.txt')

# Initialize a shared list to store the conversation history for both chatbots
conversation1 = []
conversation2 = []

# Read the content of the files containing the chatbots' prompts
chatbot2 = open_file('simbot2.txt')
chatbot1 = open_file('simbot1.txt')

# Define a function to make an API call to the OpenAI ChatCompletion endpoint
def chatgpt(api_key, conversation_list, chatbot, user_input, temperature=0.75, frequency_penalty=0.2, presence_penalty=0):
    # Set the API key
    openai.api_key = api_key

    # Update conversation by appending the user's input
    conversation_list.append({"role": "user","content": user_input})

    # Insert prompt into message history
    messages_input = conversation_list.copy()
    prompt = [{"role": "system", "content": chatbot}]
    messages_input.insert(0, prompt[0])

    # Make an API call to the ChatCompletion endpoint with the updated messages
    completion = openai.ChatCompletion.create(
        model="gpt-4-0613",
        temperature=temperature,
        frequency_penalty=frequency_penalty,
        presence_penalty=presence_penalty,
        messages=messages_input)

    # Extract the chatbot's response from the API response
    chat_response = completion['choices'][0]['message']['content']

    # Update conversation by appending the chatbot's response
    conversation_list.append({"role": "assistant", "content": chat_response})

    # Return the chatbot's response
    return chat_response

def text_to_speech(text, voice_id, api_key):
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream?optimize_streaming_latency=2'
    headers = {
        'accept': '*/*',
        'xi-api-key': api_key,
        'Content-Type': 'application/json'
    }
    data = {
        'text': text,
        'model_id': 'eleven_monolingual_v1',
        'voice_settings': {
            'stability': 0.6,
            'similarity_boost': 0.85
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if response.status_code == 200:
        with open('output.mp3', 'wb') as f:
            f.write(response.content)

        audio = AudioSegment.from_mp3('output.mp3')
        play(audio)

    else:
        print('Error:', response.text)

# Define a function to generate images using the Stability API
def generate_image(api_key, text_prompt, height=512, width=512, cfg_scale=10, clip_guidance_preset="FAST_BLUE", steps=70, samples=1):
    api_host = 'https://api.stability.ai'
    engine_id = "stable-diffusion-xl-beta-v2-2-2"

    response = requests.post(
        f"{api_host}/v1/generation/{engine_id}/text-to-image",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        },
        json={
            "text_prompts": [
                {
                    "text": text_prompt
                }
            ],
            "cfg_scale": cfg_scale,
            "clip_guidance_preset": clip_guidance_preset,
            "height": height,
            "width": width,
            "samples": samples,
            "steps": steps,
        },
    )

    if response.status_code != 200:
        raise Exception("Non-200 response: " + str(response.text))

    data = response.json()
    image_data = data["artifacts"][0]["base64"]

    # Save the generated image to a file with a unique name in the "SDimages" folder
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    image_filename = f"generated_image_{timestamp}.png"
    image_filepath = os.path.join("SDimages", image_filename)

    with open(image_filepath, "wb") as f:
        f.write(base64.b64decode(image_data))

    return image_filename

# Add a function to print text in green if it contains certain keywords
def print_colored(agent, text):
    agent_colors = {
        "Lily:": Fore.YELLOW,
        "Ethan:": Fore.CYAN,
    }

    color = agent_colors.get(agent, "")

    print(color + f"{agent}: {text}" + Style.RESET_ALL, end="")

# Define the voice IDs for both chatbots
voice_id1 = 'Your Voice ID'
voice_id2 = 'Your Voice ID'

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index4.html")
    
@app.route('/text_to_speech', methods=['POST'])
def text_to_speech_route():
    text = request.form.get('text')
    voice_id = request.form.get('voice_id')
    text_to_speech(text, voice_id, elapikey)
    return jsonify({'status': 'success'})


@app.route("/image/<path:path>")
def serve_image(path):
    return send_from_directory("SDimages", path)

num_turns = 10

# Set the initial message for the conversation
intro = "Alex is on a date with his dream girl Emily. He is very nervous and is kinda expecting Emily to turn him down. Lets see how this works out"

# Set the initial message for the conversation
initial_message = "Hello, nice too meet you!"

@app.route('/chat', methods=['POST'])
def chat():
    # Extract user input from the request
    user_input = request.form.get('user_input')

    # Check if the conversation is empty, and if so, use the initial message instead
    if not conversation1 and not conversation2:
        user_input = initial_message

    # Chatbot1 conversation
    response = chatgpt(api_key, conversation1, chatbot1, user_input)

    if "generate_image:" in response:
        image_prompt = response.split("generate_image:")[1].strip()
        image_path1 = generate_image(sd_api_key, image_prompt)
    else:
        image_path1 = None

    # Chatbot2 conversation
    response = chatgpt(api_key, conversation2, chatbot2, response)

    if "generate_image:" in response:
        image_prompt = response.split("generate_image:")[1].strip()
        image_path2 = generate_image(sd_api_key, image_prompt)
    else:
        image_path2 = None

    chatbot1_response = re.sub(r'(Response:|Narration:|Image: generate_image:.*|)', '', conversation1[-1]['content']).strip()
    chatbot2_response = re.sub(r'(Response:|Narration:|Image: generate_image:.*|)', '', response).strip()

    # Perform analysis and update the results.txt
    anal = open_file("analysis.txt").replace("<<CON>>", json.dumps(conversation1 + conversation2))
    anal2 = chatgpt(api_key, conversation1 + conversation2, "Here is the conversation:", "ANALYSE THE CONVERSATION ABOVE FOR: SENTIMENT: TONE: HUMOR AND CREATIVITY: ETHICAL AND MORAL CONSIDERATIONS: EMPATHY AND INTERPERSONAL SKILLS: GOAL-ORIENTATION: TOPIC MODELING: LEARNING AND ADAPTATION: PERSONALITY TRAITS:")

    # Instead of 'save_file', we will open the file in 'w' mode to overwrite the content every time
    with open("results.txt", "w", encoding="utf-8") as f:
        f.write(anal2)

    # Return the chatbot's responses and image paths (if any) as a JSON object
    return jsonify({'response2': chatbot1_response, 'response1': chatbot2_response, 'image_path2': image_path1, 'image_path1': image_path2})
       
@app.route("/get_analysis")
def get_analysis():
    analysis_text = open_file("results.txt")
    return jsonify({"analysis": analysis_text})
    
@app.route("/get_intro")
def get_intro():
    return jsonify({"intro": intro})
    
if __name__ == "__main__":
    app.run(debug=True, port=8000)
