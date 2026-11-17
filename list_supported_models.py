import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
client = genai.Client()
models = client.models.list()
print('Supported generateContent models:')
for m in models:
    if m.supported_actions and 'generateContent' in m.supported_actions:
        print(m.name)
