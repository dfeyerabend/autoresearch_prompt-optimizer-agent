import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    max_tokens=100,
    messages=[{"role": "user", "content": "Antworte mit genau einem Wort: Hallo"}]
)

print(response.choices[0].message.content)