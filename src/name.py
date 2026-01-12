from dotenv import load_dotenv
import os
from openai import OpenAI

# Explicitly point to the project root where your .env is
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

print("API Key loaded:", os.getenv("OPENAI_API_KEY") is not None)


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Say hello!"}]
)

print(response.choices[0].message["content"])
