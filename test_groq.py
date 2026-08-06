import os
import django
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'GETMECARE.settings')
django.setup()

from django.conf import settings

api_key = settings.GROQ_API_KEY
print(f"API Key loaded: {api_key[:20]}...")

url = "https://api.groq.com/openai/v1/chat/completions"

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

payload = {
    "model": "llama-3.3-70b-versatile",
    "messages": [
        {
            "role": "system",
            "content": "You are a helpful assistant."
        },
        {
            "role": "user",
            "content": "Hello! Can you help me?"
        }
    ],
    "temperature": 0.7,
    "max_tokens": 100
}

try:
    response = requests.post(url, headers=headers, json=payload, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {data['choices'][0]['message']['content']}")
        print("\n✓ Groq API integration is working!")
    else:
        print(f"Error: {response.text}")
except Exception as e:
    print(f"Exception: {str(e)}")
