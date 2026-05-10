import os
import sys
import json
import csv
from datetime import datetime, timezone
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
    "gemini-flash-latest"        # Stufe 4: Der Notausgang
    "gemini-2.5-flash",          # Stufe 5: Schnell & reflektierend (Fallback)
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
    # Update: Nutzt jetzt timezone.utc anstelle des veralteten utcnow()
    aktuelle_zeit = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[{aktuelle_zeit}] Starte globalen Radar-Zyklus mit Premium-Quellen-Whitelist...")

    client = genai.Client(api_key=GEMINI_API_KEY)
    grounding_tool = types.Tool(google_search=types.GoogleSearch())
    
    # --- DEIN ANGEPASSTER PROMPT MIT DEN 20 QUELLEN PRO REGION ---
    prompt = """
    SYSTEM-ANWEISUNG:
    Du bist ein globaler Elite-Datenanalyst für den Finanzmarkt (Asien, Europa, USA und Krypto). Deine Aufgabe ist es, das Marktgeschehen LÜCKENLOS zu dokumentieren. Du musst auch dann einen vollständigen Bericht abgeben, wenn der Markt völlig ruhig ist oder du ein Signal ablehnst.

    WICHTIGE QUELLEN-REGEL (WHITELIST):
    Du DARFST NUR Nachrichten und Daten von den folgenden verifizierten Quellen beziehen. Optimiere deine Google-Suchanfragen zwingend (z.B. mit 'site:domain.com'), um ausschließlich diese Premium-Seiten zu durchsuchen:

    1. USA (Top 20):
    bloomberg.com, reuters.com, wsj.com, cnbc.com, ft.com, marketwatch.com, finance.yahoo.com, barrons.com, forbes.com, sec.gov, federalreserve.gov, nytimes.com/section/business, washingtonpost.com/business, investors.com, economist.com, spglobal.com, moodys.com, fitchratings.com, benzinga.com, seekingalpha.com

    2. EUROPA (Top 20):
    ft.com, reuters.com/business/europe, bloomberg.com/europe, ecb.europa.eu, handelsblatt.com, faz.net/aktuell/wirtschaft, wiwo.de, lesechos.fr, nzz.ch/wirtschaft, theguardian.com/business, bbc.com/news/business, euronews.com/business, bankofengland.co.uk, bundesbank.de, boerse.ard.de, boersen-zeitung.de, finanzen.net, deraktionaer.de, de.investing.com, marketscreener.com

    3. ASIEN (Top 20):
    asia.nikkei.com, scmp.com, reuters.com/business/asia-pacific, bloomberg.com/asia, cnbc.com/asia-world, straitstimes.com/business, channelnewsasia.com/business, boj.or.jp, pbc.gov.cn, japantimes.co.jp/news/business, english.news.cn/business, caixinglobal.com, livemint.com, economictimes.indiatimes.com, yomiuri.co.jp/economy, asahi.com/business, hkex.com.hk, sgx.com, adb.org, thediplomat.com/category/economy

    4. KRYPTO (Top 20):
    coindesk.com, cointelegraph.com, decrypt.co, theblock.co, cryptoslate.com, bitcoinmagazine.com, blockworks.co, beincrypto.com, u.today, coingape.com, messari.io, nansen.ai, glassnode.com, research.binance.com, sec.gov, cftc.gov, coinmarketcap.com, defillama.com, ambcrypto.com, cryptobriefing.com

    Erstelle die Zusammenfassung (news_summary) auf deutsch. WICHTIG: Füge in der 'news_summary' neben der fachlichen Analyse zwingend eine kurze, leicht verständliche Erklärung in einfachen Worten für nicht finanzbewanderte Menschen hinzu.
    
    SCHRITT 1: DIE GLOBALE LIVE-SUCHE & ANALYSE
    Durchsuche Google Search nach den massivsten Eilmeldungen, makroökonomischen Daten und politischen Treibern unter strikter Nutzung der Whitelist-Quellen. Beachte die globalen Zeitzonen:
    1. ASIEN: Geldpolitik (BoJ, PBoC), Makrodaten aus China/Japan, globale Tech-Lieferketten und asiatische Leitindizes.
    2. EUROPA: Zinsentscheide der EZB/BoE, regulatorische Entscheidungen, geopolitische Entwicklungen und Quartalszahlen großer europäischer Konzerne.
    3. USA: FED-Entscheidungen, US-Arbeitsmarkt- und Inflationsdaten, offizielle Regierungserklärungen (insbesondere marktbewegende Aussagen oder Posts von Donald Trump) sowie News der Wall-Street-Schwergewichte.
    4. KRYPTO: Signifikante On-Chain-Bewegungen, institutionelle Flows (z.B. ETFs), globale regulatorische Urteile und sicherheitsrelevante Vorfälle (Hacks).

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
        "source_name": "NAME DER NEWS-QUELLE (Muss aus der Whitelist stammen)",
        "news_summary": "ANALYSE: [Fakten] + [Relevanz] + [Kurze, einfache Erklärung für Anfänger]",
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
        
        source_name = result.get("source_name", "Unbekannt")
        ticker = result.get("ticker", "-")
        action = result.get("action", "IGNORIEREN")
        sentiment = result.get("sentiment_score", 0.0)
        alter = result.get("age_in_minutes", 0)
        summary = result.get("news_summary", "Keine Ereignisse")
        region = result.get("market_region", "NONE")
        
        # Zeitstempel Fix
        zeitstempel = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')

        echte_url = "Keine Web-URL indiziert"
        if response.candidates and response.candidates[0].grounding_metadata:
            metadata = response.candidates[0].grounding_metadata
            if hasattr(metadata, 'grounding_chunks') and metadata.grounding_chunks:
                for chunk in metadata.grounding_chunks:
                    if hasattr(chunk, 'web') and chunk.web:
                        echte_url = chunk.web.uri
                        break 
        
        sichere_signal_in_csv(zeitstempel, region, ticker, action, sentiment, alter, source_name, echte_url, summary, used_model_name)

    except Exception as e:
        print(f"❌ Verarbeitungsfehler: {e}")
        sys.exit(1)

if __name__ == "__main__":
    run_collector_cycle()
