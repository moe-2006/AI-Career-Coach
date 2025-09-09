import os
import openai
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Check if API key is loaded
print("OPENAI_API_KEY:", os.getenv("OPENAI_API_KEY"))

openai.api_key = os.getenv("OPENAI_API_KEY")

try:
    # Simple test: list available models
    models = openai.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": "Hello!"}]
    )
    print("API call successful! Response:")
    print(models.choices[0].message.content)
except Exception as e:
    print("Error:", e)
