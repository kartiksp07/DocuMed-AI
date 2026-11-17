import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
# Ensure API key is read from .env automatically by genai
models = genai.list_models()
print('Available models:')
for m in models:
    print(m.name)
