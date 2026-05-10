import os
import json
import csv
from datetime import datetime
from google import genai
from google.genai import types

# --- 1. SYSTEM-PRÜFUNG ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("Systemfehler: Umgebungsvariable 'GEMINI_API_KEY' fehlt.")

# Datei, in der wir die Historie sammeln
LOG_FILE = "signals_log.csv"

def sichere_signal_in_csv(zeitstempel, signal_typ, ticker, action, sentiment, alter, url, summary):
    """Schreibt das erkannte Signal als neue Zeile in die CSV-Datei."""
    datei_existiert = os.path.isfile(LOG_FILE)
    
    with open(LOG_FILE, mode='a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Wenn die Datei neu ist, schreiben wir zuerst die Kopfzeile (Header)
        if not datei_existiert:
            writer.writerow(["Zeitstempel (UTC)", "Signal-Typ", "Ticker", "Handlung", "Sentiment", "Alter (Min)", "Original-Quelle", "Zusammenfassung"])
        
        writer.writerow([zeitstempel, signal_typ, ticker, action, sentiment, alter, url, summary])
    print(f"💾 Signal für {ticker} erfolgreich in {LOG_FILE} gespeichert.")

def run_collector_cycle():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starte reinen Gemini-Suchzyklus...")

    # Initialisierung des aktuellen SDKs mit Live-Suche (Grounding)
    client = genai.Client(api_key=GEMINI_API_KEY)
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    
    config = types.GenerateContentConfig(
        temperature=0.2, # Niedrige Temperatur für harte Faktenanalyse
        tools=[grounding_tool],
        response_mime_type="application/json"
    )

    # Der isolierte Prüf-Prompt (Fokus auf Marktsuche ohne Portfolio-Abhängigkeit)
    prompt = """
    SYSTEM-ANWEISUNG:
    Du bist ein neutraler, hochpräziser Daten-Analyst für den Finanzmarkt.
    
    SCHRITT 1: DIE DUALE LIVE-SUCHE
    Durchsuche Google Search nach echten, marktbewegenden Eilmeldungen der letzten 30 bis 60 Minuten:
    1. Offizielle Statements von Donald Trump (Zölle, Notenbank, Geopolitik).
    2. Eilmeldungen von REUTERS, BLOOMBERG, WSJ oder CNBC zu Makro-Daten, Unternehmenszahlen oder Krypto-Spotmärkten.

    SCHRITT 2: FILTERUNG
    - Zeitfilter: Meldungen, deren tatsächliche Veröffentlichung länger als 60 Minuten zurückliegt, MÜSSEN ignoriert werden (Alpha-Verfall).
    - Clickbait-Filter: Reißerische Überschriften ignorieren. Nur harte Fakten im Textkörper zählen.

    SCHRITT 3: JSON-AUSGABE
    Finde exakt die EINE relevanteste, frische Nachricht und antworte AUSSCHLIESSLICH in diesem JSON-Format:
    {
        "signal_found": true,
        "signal_type": "TRUMP_DIRECT" oder "GENERAL_MACRO",
        "ticker": "SYMBOL",
        "news_summary": "Faktenbasierte Zusammenfassung ohne Clickbait",
        "age_in_minutes": 15,
        "sentiment_score": 0.8, 
        "confidence": 95,
        "action": "KAUFEN" oder "VERKAUFEN" oder "IGNORIEREN"
    }

    REGELN:
    - 'action': Nur auf KAUFEN oder VERKAUFEN setzen, wenn confidence >= 85 UND abs(sentiment_score) >= 0.6 ist. Ansonsten IMMER 'IGNORIEREN'.
    - Wenn keine relevanten News existieren, setze signal_found auf false.
    """

    try:
        print("🔍 Durchsuche das Web und analysiere Daten...")
        response = client.models.generate_content(
            model="gemini-3.1-pro",
            contents=prompt,
            config=config
        )

        result = json.loads(response.text.strip())
        
        if not result.get("signal_found") or result.get("action") == "IGNORIEREN":
            print("⏸️ Keine frischen, starken Eilmeldungen gefunden. Es wird nichts protokolliert.")
            return

        ticker = result.get("ticker")
        action = result.get("action")
        sentiment = result.get("sentiment_score")
        alter = result.get("age_in_minutes")
        summary = result.get("news_summary")
        signal_typ = result.get("signal_type")
        zeitstempel = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')

        print("=" * 80)
        print(f"⚡ VERWERTBARES SIGNAL ERKANNT: {action} {ticker}")
        
        # Echte URL fälschungssicher aus den Metadaten ziehen
        echte_url = "Keine Web-URL in Metadaten"
        if response.candidates and response.candidates[0].grounding_metadata:
            metadata = response.candidates[0].grounding_metadata
            if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                for chunk in metadata.grounding_chunks:
                    if hasattr(chunk, 'web') and chunk.web:
                        echte_url = chunk.web.uri
                        break # Primäre Quelle extrahieren
                        
        print(f"🔗 Quelle: {echte_url}")
        print("=" * 80)

        # In die CSV-Datei schreiben
        sichere_signal_in_csv(zeitstempel, signal_typ, ticker, action, sentiment, alter, echte_url, summary)

    except Exception as e:
        print(f"❌ Fehler bei der API-Ausführung: {e}")

if __name__ == "__main__":
    run_collector_cycle()
