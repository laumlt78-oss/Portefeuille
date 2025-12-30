import yfinance as yf
import pandas as pd
import requests
import os
import sys
from datetime import datetime, timedelta

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
flash_news = ""
all_news = ""
alertes = 0

for _, row in df.iterrows():
    try:
        tk = yf.Ticker(row['Ticker'])
        hist = tk.history(period="2d")
        
        price = hist['Close'].iloc[-1] if len(hist) >= 1 else tk.fast_info.last_price
        price_hier = hist['Close'].iloc[-2] if len(hist) >= 2 else price
            
        qte = float(row['Qté'])
        total_achat += (float(row['PRU']) * qte)
        total_actuel += (price * qte)
        total_veille += (price_hier * qte)

        # Gestion des News
        news_list = tk.news
        if news_list:
            top_news = news_list[0]
            news_title = top_news['title']
            all_news += f"- {row['Nom']} : {news_title}\n"
            
            # Pour le mode Check, on ne garde que les news très récentes (publiées aujourd'hui)
            # yfinance fournit le timestamp en secondes
            pub_time = datetime.fromtimestamp(top_news['providerPublishTime'])
            if pub_time > datetime.now() - timedelta(hours=8):
                flash_news += f"🔥 {row['Nom']} : {news_title}\n"

        # Alertes de prix
        if MODE == "check":
            if price <= float(row['Seuil_Bas']):
                send_push("⚠️ ALERTE BASSE", f"{row['Nom']} : {price:.2f}€")
                alertes += 1
            elif float(row.get('Seuil_Haut', 0)) > 0 and price >= float(row['Seuil_Haut']):
                send_push("🚀 OBJECTIF", f"{row['Nom']} : {price:.2f}€")
                alertes += 1
    except: continue

# 3. Calculs
perf_totale = ((total_actuel - total_achat) / total_achat * 100) if total_achat > 0 else 0
perf_jour = ((total_actuel - total_veille) / total_veille * 100) if total_veille > 0 else 0

# 4. Envoi
if MODE == "open":
    send_push("🔔 OUVERTURE", f"Valeur : {total_actuel:.2f}€\nPerf Totale : {perf_totale:+.2f}%")

elif MODE == "close":
    msg_news = all_news if all_news else "Pas d'actualités."
    msg = (f"Valeur : {total_actuel:.2f}€\n"
           f"Variation Jour : {perf_jour:+.2f}%\n"
           f"Perf Totale : {perf_totale:+.2f}%\n\n"
           f"📰 RECAP NEWS :\n{msg_news}")
    send_push("🏁 CLOTURE", msg)

elif MODE == "check":
    # Envoi d'un Flash Info si une news importante vient de sortir
    if flash_news:
        send_push("🗞️ FLASH INFO BOURSE", f"Nouvelles publications sur vos titres :\n\n{flash_news}")
    
    # Test manuel
    if "GITHUB_ACTIONS" in os.environ and os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        send_push("✅ Robot Actif", f"Valeur : {total_actuel:.2f}€\nJour : {perf_jour:+.2f}%\nTotal : {perf_totale:+.2f}%")
