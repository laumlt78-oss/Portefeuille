import yfinance as yf
import pandas as pd
import requests
import os
import sys
from datetime import datetime

# Configuration des secrets
USER_KEY = os.getenv("PUSHOVER_USER_KEY")
API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")
GH_REPO = os.getenv("GH_REPO")
# Détermine si on est en mode Ouverture, Clôture ou Vérification simple
MODE = sys.argv[1] if len(sys.argv) > 1 else "check"

def send_push(title, message, priority=0):
    requests.post("https://api.pushover.net/1/messages.json", data={
        "token": API_TOKEN, "user": USER_KEY, "title": title, "message": message, "priority": priority
    })

# Récupération des données du portefeuille
url = f"https://raw.githubusercontent.com/{GH_REPO}/main/portefeuille_data.csv"
try:
    df = pd.read_csv(url)
except:
    print("Erreur : Impossible de lire le fichier CSV.")
    sys.exit()

total_achat = 0
total_actuel = 0
report_news = ""

for _, row in df.iterrows():
    try:
        tk = yf.Ticker(row['Ticker'])
        # Prix actuel
        price = tk.fast_info.last_price
        if price is None or price == 0:
            price = tk.history(period="1d")['Close'].iloc[-1]
            
        pru = float(row['PRU'])
        qte = float(row['Qté'])
        total_achat += (pru * qte)
        total_actuel += (price * qte)

        # 1. Vérification des Seuils (Alertes en direct)
        if MODE == "check":
            if price <= float(row['Seuil_Bas']):
                send_push("⚠️ SEUIL BAS ATTEINT", f"{row['Nom']} : {price:.2f}€ (Alerte: {row['Seuil_Bas']}€)", 1)
            elif float(row.get('Seuil_Haut', 0)) > 0 and price >= float(row['Seuil_Haut']):
                send_push("🚀 OBJECTIF ATTEINT", f"{row['Nom']} : {price:.2f}€ (Objectif: {row['Seuil_Haut']}€)", 1)

        # 2. Préparation du rapport de News
        if MODE == "close":
            news = tk.news
            if news:
                report_news += f"- {row['Nom']} : {news[0]['title']}\n"
    except:
        continue

# 3. Logique d'envoi selon le moment de la journée
perf_globale = ((total_actuel - total_achat) / total_achat * 100) if total_achat > 0 else 0

if MODE == "open":
    send_push("🔔 OUVERTURE BOURSE", f"Valeur : {total_actuel:.2f}€\nPerf Globale : {perf_globale:+.2f}%")

elif MODE == "close":
    msg = f"Valeur Finale : {total_actuel:.2f}€\nPerf Journée : {perf_globale:+.2f}%\n\n📰 DERNIÈRES INFOS :\n{report_news}"
    send_push("🏁 CLÔTURE BOURSE", msg)

elif MODE == "check":
    send_push("TEST FINAL", "Si tu vois ce message, Pushover fonctionne!")
