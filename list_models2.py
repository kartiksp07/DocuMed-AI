import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
client = genai.Client()
# List models that support generateContent
available = []
for m in client.models.list():
    if m.supported_actions and "generateContent" in m.supported_actions:
        available.append(m.name)
print('Supported generateContent models:')
for name in available:
    print(name)
