import os
import sys
import json
import csv
from datetime import datetime
from google import genai
from google.genai import types

# --- 1. SYSTEM-PRÜFUNG ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("❌ FATALER FEHLER: Umgebungsvariable 'GEMINI_API_KEY' fehlt.")
    sys.exit(1)

LOG_FILE = "signals_log.csv"

# --- 2. MODEL-KASKADE (Exakt nach deiner Liste) ---
MODELS_TO_TRY = [
    "gemini-3.1-pro-preview",    # Prio 1: Dein 3.1 Pro (Aktuell im Limit)
    "gemini-2.5-pro",            # Prio 2: Enorme Tiefe & stabil (Dein "Thinking"-Ersatz)
    "gemini-2.5-flash"           # Prio 3: Hohe Quote & zuverlässig
]

def sichere_signal_in_csv(zeitstempel, region, ticker, action, sentiment, alter, url, summary, model_used):
    datei_existiert = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not datei_existiert:
            writer.writerow(["Zeitstempel (UTC)", "Region", "Ticker", "Handlung", "Sentiment", "Alter (Min)", "Original-Quelle", "Zusammenfassung", "KI-Modell"])
        writer.writerow([zeitstempel, region, ticker, action, sentiment, alter, url, summary, model_used])
    print(f"💾 Log-Eintrag ({model_used}) gesichert.")

def run_collector_cycle():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starte Zyklus mit Modell-Fallback...")

    client = genai.Client(api_key=GEMINI_API_KEY)
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    
    # --- DEIN ORIGINAL-PROMPT (KOMPLETT UNVERÄNDERT) ---
    prompt = """
    SYSTEM-ANWEISUNG:
    Du bist ein globaler Elite-Datenanalyst für den Finanzmarkt (Asien, Europa, USA und Krypto). Deine Aufgabe ist es, das Marktgeschehen LÜCKENLOS zu dokumentieren. Du musst auch dann einen vollständigen Bericht abgeben, wenn der Markt völlig ruhig ist oder du ein Signal ablehnst.
    
    SCHRITT 1: DIE GLOBALE LIVE-SUCHE
    Durchsuche Google Search nach den massivsten Eilmeldungen und politischen Treibern in Asien, Europa, den USA oder am Krypto-Spotmarkt.

    SCHRITT 2: DIE WOCHENEND- & LÜCKEN-LOGIK (GAP RISK)
    - Krypto-Assets (BTC, ETH): Handeln 24/7. Hier gilt immer ein strikter 60-Minuten-Verfall.
    - Regulierte Aktien/ETFs weltweit: Wenn heute MONTAG ist (oder Sonntagabend vor den asiatischen Öffnungen), ignoriere das Alter der Nachricht. Meldungen vom gesamten Wochenende MÜSSEN akkumuliert werden.
      * Asien-Assets entladen sich ab ca. 02:00 Uhr nachts (MEZ).
      * Europa-Assets entladen sich ab 09:00 Uhr morgens (MEZ).
      * US-Assets entladen sich ab 15:30 Uhr (MEZ).

    SCHRITT 3: JSON-AUSGABE
    Bewerte die aktuelle Lage. Gibt es eine starke Eilmeldung, extrahiere sie. Ist der Markt ruhig, unspektakulär oder voller Clickbait, dokumentiere exakt diesen Zustand.
    
    Antworte AUSSCHLIESSLICH in diesem JSON-Format:
    {
        "signal_found": true,
        "market_region": "ASIA" oder "EUROPE" oder "USA" oder "CRYPTO" oder "NONE",
        "ticker": "OFFIZIELLES_SYMBOL" oder "-", 
        "news_summary": "Faktenbasierte Zusammenfassung der News ODER eine kurze Begründung, warum der Markt gerade ruhig ist / die News ignoriert werden.",
        "age_in_minutes": 0, 
        "sentiment_score": 0.0, 
        "confidence": 0,
        "action": "KAUFEN" oder "VERKAUFEN" oder "IGNORIEREN"
    }

    REGELN:
    - 'action': Setze dies NUR auf KAUFEN oder VERKAUFEN, wenn confidence >= 85 UND abs(sentiment_score) >= 0.6 ist. Ansonsten MUSS hier 'IGNORIEREN' stehen.
    - WICHTIG: Auch wenn du 'IGNORIEREN' wählst, fülle das JSON komplett aus, damit die lückenlose Datenbank gefüttert wird.
    """

    response = None
    used_model_name = None

    for model_name in MODELS_TO_TRY:
        try:
            print(f"🤖 Versuche Modell: {model_name}...")
            
            # JSON-Modus nur bei Pro-Modellen (3.1 und 2.5) erzwingen
            mime_type = "application/json" if "pro" in model_name else "text/plain"
            
            config = types.GenerateContentConfig(
                temperature=0.2, 
                tools=[grounding_tool],
                response_mime_type=mime_type
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config
            )
            used_model_name = model_name
            break 
        except Exception as e:
            # Wir fangen Ressourcen-Limits (429) und andere Fehler ab
            print(f"⚠️ {model_name} nicht verfügbar: {e}")
            continue

    if not response or not used_model_name:
        print("❌ Alle Modelle in deiner Liste sind aktuell nicht erreichbar.")
        sys.exit(1)

    try:
        raw_text = response.text.strip()
        # Falls ein Fallback-Modell (text/plain) Markdown nutzt, säubern wir es
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        
        result = json.loads(raw_text)
        
        ticker = result.get("ticker", "-")
        action = result.get("action", "IGNORIEREN")
        sentiment = result.get("sentiment_score", 0.0)
        alter = result.get("age_in_minutes", 0)
        summary = result.get("news_summary", "Keine Ereignisse")
        region = result.get("market_region", "NONE")
        zeitstempel = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        echte_url = "Keine Web-URL indiziert"
        if response.candidates and response.candidates[0].grounding_metadata:
            metadata = response.candidates[0].grounding_metadata
            if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                for chunk in metadata.grounding_chunks:
                    if hasattr(chunk, 'web') and chunk.web:
                        echte_url = chunk.web.uri
                        break 
                        
        sichere_signal_in_csv(zeitstempel, region, ticker, action, sentiment, alter, echte_url, summary, used_model_name)

    except Exception as e:
        print(f"❌ Fehler bei der JSON-Verarbeitung: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_collector_cycle()
