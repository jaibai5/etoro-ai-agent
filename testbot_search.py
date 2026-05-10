import os
from google import genai

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

print("--- DEINE VERFÜGBAREN MODELLE (2026 UPDATE) ---")
try:
    for model in client.models.list():
        # Hier nutzen wir jetzt 'supported_actions' wie vom System vorgeschlagen
        if "generate_content" in model.supported_actions or "generateContent" in model.supported_actions:
            print(f"ID: {model.name} | Name: {model.display_name}")
except Exception as e:
    print(f"Fehler beim Abrufen der Liste: {e}")
print("-----------------------------------------------")
