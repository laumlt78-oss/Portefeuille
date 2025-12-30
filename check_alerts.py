import yfinance as yf
import pandas as pd
import requests
import os
import sys

# Configuration
USER_KEY = os.getenv("PUSHOVER_USER_KEY")
API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")
GH_REPO = os.getenv("GH_REPO")
MODE = sys.argv[1] if len(sys.argv) > 1 else "check"

def send_push(title, message):
    payload = {"token": API_TOKEN, "user": USER_KEY, "title": title, "message": message}
    requests.post("https://api.pushover.net/1/messages.json", data=payload)

# 1. Lecture du fichier
url = f"https://raw.githubusercontent.com/{GH_REPO}/main/portefeuille_data.csv"
try:
    df = pd.read_csv(url)
except:
    url = f"https://raw.githubusercontent.com/{GH_REPO}/master/portefeuille_data.csv"
    df = pd.read_csv(url)

# 2. Analyse
total_achat = 0
total_actuel = 0
total_veille = 0
report_news = ""
alertes = 0

for _, row in df.iterrows():
    try:
        tk = yf.Ticker(row['Ticker'])
        # On récupère 2 jours d'historique pour avoir le prix actuel et celui d'hier
        hist = tk.history(period="2d")
        
        if len(hist) < 2:
            # Sécurité pour les jours fériés ou IPO récentes
            price = tk.fast_info.last_price
            price_hier = price
        else:
            price = hist['Close'].iloc[-1]
            price_hier = hist['Close'].iloc[-2]
            
        qte = float(row['Qté'])
        total_achat += (float(row['PRU']) * qte)
        total_actuel += (price * qte)
        total_veille += (price_hier * qte)

        if MODE == "check":
            if price <= float(row['Seuil_Bas']):
                send_push("⚠️ ALERTE BASSE", f"{row['Nom']} : {price:.2f}€")
                alertes += 1
            elif float(row.get('Seuil_Haut', 0)) > 0 and price >= float(row['Seuil_Haut']):
                send_push("🚀 OBJECTIF", f"{row['Nom']} : {price:.2f}€")
                alertes += 1
        
        if MODE == "close":
            news = tk.news
            if news: report_news += f"- {row['Nom']} : {news[0]['title']}\n"
    except: continue

# 3. Calculs des performances
perf_totale = ((total_actuel - total_achat) / total_achat * 100) if total_achat > 0 else 0
perf_jour = ((total_actuel - total_veille) / total_veille * 100) if total_veille > 0 else 0

# 4. Envoi selon le mode
if MODE == "open":
    msg = f"Valeur : {total_actuel:.2f}€\nPerf Totale : {perf_totale:+.2f}%"
    send_push("🔔 OUVERTURE", msg)

elif MODE == "close":
    msg_news = report_news if report_news else "Pas d'actualités."
    msg = (f"Valeur : {total_actuel:.2f}€\n"
           f"Variation Jour : {perf_jour:+.2f}%\n"
           f"Perf Totale : {perf_totale:+.2f}%\n\n"
           f"📰 NEWS :\n{msg_news}")
    send_push("🏁 CLOTURE", msg)

elif MODE == "check":
    # Toujours inclure les deux perfs dans le test manuel
    if "GITHUB_ACTIONS" in os.environ and os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        msg = (f"Analyse finie.\nValeur : {total_actuel:.2f}€\n"
               f"Jour : {perf_jour:+.2f}%\nTotal : {perf_totale:+.2f}%")
        send_push("✅ Robot Actif", msg)
