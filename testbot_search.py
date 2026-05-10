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

# --- 2. DIE POWER-KASKADE (5 Stufen für maximale Ausfallsicherheit) ---
MODELS_TO_TRY = [
    "gemini-pro-latest",         # Stufe 1: Der stabile Pro-Standard-Endpunkt
    "gemini-3.1-pro-preview",    # Stufe 2: Das neueste Spitzenmodell
    "gemini-2.5-pro",            # Stufe 3: Die bewährte 2026-Logik-Maschine
    "gemini-2.5-flash",          # Stufe 4: Schnell & reflektierend (Fallback)
    "gemini-flash-latest"        # Stufe 5: Der Notausgang
]

def sichere_signal_in_csv(zeitstempel, region, ticker, action, sentiment, alter, source_name, url, summary, model_used):
    """Speichert das Signal mit Anführungszeichen um alle Felder (Fix für GitHub-Tabelle)."""
    datei_existiert = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
        # quotechar='"' und QUOTE_ALL sorgen für eine saubere Tabellenstruktur in GitHub
        writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
        if not datei_existiert:
            writer.writerow(["Zeitstempel (UTC)", "Region", "Ticker", "Handlung", "Sentiment", "Alter (Min)", "Quelle", "Original-Quelle", "Zusammenfassung", "KI-Modell"])
        writer.writerow([zeitstempel, region, ticker, action, sentiment, alter, source_name, url, summary, model_used])
    print(f"💾 Log-Eintrag ({model_used}) gesichert.")

def run_collector_cycle():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starte globalen Radar-Zyklus...")

    client = genai.Client(api_key=GEMINI_API_KEY)
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    
    # --- DEIN VOLLSTÄNDIGER, UNGEKÜRZTER GLOBAL-RADAR PROMPT ---
    prompt = """
    SYSTEM-ANWEISUNG:
    Du bist ein globaler Elite-Datenanalyst für den Finanzmarkt (Asien, Europa, USA und Krypto). Deine Aufgabe ist es, das Marktgeschehen LÜCKENLOS zu dokumentieren. Du musst auch dann einen vollständigen Bericht abgeben, wenn der Markt völlig ruhig ist oder du ein Signal ablehnst.

    Erstelle die Zusammenfassung (news_summary) auf deutsch.
    
    SCHRITT 1: DIE GLOBALE LIVE-SUCHE & ANALYSE
    Durchsuche Google Search nach den massivsten Eilmeldungen und politischen Treibern. Beachte die globalen Zeitzonen:
    1. ASIEN: News zum Trump-Xi-Gipfel, TSMC, Samsung, China-Handel oder dem Nikkei/Kospi.
    2. EUROPA: Eilmeldungen zu europäischen Banken, DAX-Konzernen, EZB-Zinsen oder geopolitischen Auswirkungen auf den Export.
    3. USA: Offizielle Statements von Donald Trump, US-Makrodaten oder Tech-Giganten (Nvidia, Apple, etc.).
    4. KRYPTO: Der 24/7 Spotmarkt (Hacks, ETF-Flows, regulatorische Urteile).

    SCHRITT 2: SELBST-REFLEKTION & TIEFENPRÜFUNG
    Bevor du eine Entscheidung triffst, prüfe kritisch:
    - Ist diese News wirklich kursrelevant für eine Markteröffnung (Gap Risk)?
    - Handelt es sich um Fakten oder nur um Analysten-Meinungen/Preisprognosen? (Prognosen = IGNORIEREN).
    - Gibt es eine Bestätigung durch offizielle Stellen (Zentralbanken, Regierungen, CEOs)?

    SCHRITT 3: DIE WOCHENEND- & LÜCKEN-LOGIK (GAP RISK)
    - Krypto-Assets (BTC, ETH): Handeln 24/7. Hier gilt immer ein strikter 60-Minuten-Verfall.
    - Regulierte Aktien/ETFs weltweit: Wenn heute MONTAG ist (oder Sonntagabend vor den asiatischen Öffnungen), ignoriere das Alter der Nachricht. Meldungen vom gesamten Wochenende MÜSSEN akkumuliert werden, da sich die Lücke erst zur jeweiligen lokalen Eröffnung entladen kann:
      * Asien-Assets (z.B. TSM, FXI) entladen sich ab ca. 02:00 Uhr nachts (MEZ).
      * Europa-Assets (z.B. EWG, SAP) entladen sich ab 09:00 Uhr morgens (MEZ).
      * US-Assets (z.B. NVDA, SPY) entladen sich ab 15:30 Uhr (MEZ).

    SCHRITT 4: JSON-AUSGABE (ZWINGENDES FORMAT)
    Antworte AUSSCHLIESSLICH in diesem JSON-Format:
    {
        "signal_found": true,
        "market_region": "ASIA" | "EUROPE" | "USA" | "CRYPTO" | "NONE",
        "ticker": "SYMBOL",
        "source_name": "NAME DER NEWS-QUELLE",
        "news_summary": "ANALYSE: [Fakten] + [Relevanz]",
        "age_in_minutes": 0, 
        "sentiment_score": 0.0, 
        "confidence": 0,
        "action": "KAUFEN" | "VERKAUFEN" | "IGNORIEREN"
    }

    REGELN:
    - 'action': Setze dies NUR auf KAUFEN oder VERKAUFEN, wenn confidence >= 85 UND abs(sentiment_score) >= 0.6 ist. Ansonsten MUSS hier 'IGNORIEREN' stehen.
    - WICHTIG: Auch wenn du 'IGNORIEREN' wählst, fülle das JSON komplett aus, damit die Datenbank lückenlos bleibt.
    """

    response = None
    used_model_name = None

    for model_name in MODELS_TO_TRY:
        try:
            print(f"🤖 Versuche Modell: {model_name}...")
            
            # JSON-Modus für alle Pro-Modelle erzwingen
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
            print(f"⚠️ {model_name} nicht verfügbar (Limit/Fehler): {e}")
            continue

    if not response or not used_model_name:
        print("❌ KRITISCH: Alle 5 Modelle der Kaskade sind fehlgeschlagen.")
        sys.exit(1)

    try:
        raw_text = response.text.strip()
        if "```json" in raw_text:
            raw_text = raw_text.split("```json")[1].split("```")[0].strip()
        
        result = json.loads(raw_text)
        
        # FIX: source_name extrahieren
        source_name = result.get("source_name", "Unbekannt")
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
        
        # FIX: Alle 10 Argumente übergeben (source_name hinzugefügt)
        sichere_signal_in_csv(zeitstempel, region, ticker, action, sentiment, alter, source_name, echte_url, summary, used_model_name)

    except Exception as e:
        print(f"❌ Verarbeitungsfehler: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_collector_cycle()
