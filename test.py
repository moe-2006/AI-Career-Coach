import os, openai
openai.api_key = os.getenv("OPENAI_API_KEY")

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[{"role": "user", "content": "Say hi in JSON like: {\"message\": \"Hi\"}"}]
)
print(response.choices[0].message.content)