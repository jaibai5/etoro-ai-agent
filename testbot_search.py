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
    Du bist ein globaler Elite-Datenanalyst für den Finanzmarkt (Asien, Europa, USA und Krypto). Deine Spezialität ist das Abgreifen von aufgestauter Wochenend-Spannung (Weekend Gaps) zum jeweiligen lokalen Börsenstart.
    
    SCHRITT 1: DIE GLOBALE LIVE-SUCHE
    Durchsuche Google Search nach den massivsten Eilmeldungen und politischen Treibern. Beachte die globalen Zeitzonen:
    1. ASIEN: News zum Trump-Xi-Gipfel, TSMC, Samsung, China-Handel oder dem Nikkei/Kospi.
    2. EUROPA: Eilmeldungen zu europäischen Banken, DAX-Konzernen, EZB-Zinsen oder geopolitischen Auswirkungen auf den Export.
    3. USA: Offizielle Statements von Donald Trump, US-Makrodaten oder Tech-Giganten.
    4. KRYPTO: Der 24/7 Spotmarkt.

    SCHRITT 2: DIE WOCHENEND- & LÜCKEN-LOGIK (GAP RISK)
    - Krypto-Assets (BTC, ETH): Handeln 24/7. Hier gilt immer ein strikter 60-Minuten-Verfall.
    - Regulierte Aktien/ETFs weltweit: Wenn heute MONTAG ist (oder Sonntagabend vor den asiatischen Öffnungen), ignoriere das Alter der Nachricht. Meldungen vom gesamten Wochenende MÜSSEN akkumuliert und als brandheiß eingestuft werden, da sich die Lücke erst zur jeweiligen lokalen Eröffnung entladen kann:
      * Asien-Assets (z.B. TSM, FXI) entladen sich ab ca. 02:00 Uhr nachts (MEZ).
      * Europa-Assets (z.B. EWG, SAP) entladen sich ab 09:00 Uhr morgens (MEZ).
      * US-Assets (z.B. NVDA, SPY) entladen sich ab 15:30 Uhr (MEZ).

    SCHRITT 3: JSON-AUSGABE
    Finde global exakt die EINE Nachricht mit dem absolut höchsten Lücken- oder Intraday-Potenzial und antworte AUSSCHLIESSLICH in diesem JSON-Format:
    {
        "signal_found": true,
        "market_region": "ASIA" oder "EUROPE" oder "USA" oder "CRYPTO",
        "ticker": "OFFIZIELLES_SYMBOL", 
        "news_summary": "Faktenbasierte Zusammenfassung ohne Clickbait",
        "age_in_minutes": 1150, 
        "sentiment_score": 0.9, 
        "confidence": 95,
        "action": "KAUFEN" oder "VERKAUFEN" oder "IGNORIEREN"
    }

    REGELN:
    - 'action': Nur auf KAUFEN/VERKAUFEN setzen, wenn confidence >= 85 UND abs(sentiment_score) >= 0.6.
    - Wähle als 'ticker' das am besten passende, international handelbare Symbol (z.B. TSM für Taiwan Semiconductor, EWG für Deutschland, FXI für China, oder direkte Aktien-Ticker).
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
