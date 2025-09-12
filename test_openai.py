### THIS IS TO TEST YOUR OPEN AI KEY AND SEE WHAT MODELS ARE AVAILABLE TO YOU BASED OFF THE GIVEN KEY

from dotenv import load_dotenv
import os
import openai

load_dotenv()  # Load .env variables
openai.api_key = os.getenv("OPENAI_API_KEY")

# Test the key by listing available models (works in the old API)
try:
    models = openai.Model.list()  # old API
    print("API key works! Here are some models:")
    for m in models['data'][:5]:
        print(m['id'])
except Exception as e:
    print("API key failed:", e)