import os
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

print("--- DEINE VERFÜGBAREN MODELLE ---")
for model in client.models.list():
    # Wir filtern nach Modellen, die Text generieren können
    if "generateContent" in model.supported_methods:
        print(f"ID: {model.name} | Name: {model.display_name}")
print("---------------------------------")
