import yfinance as yf
import pandas as pd
import requests
import os

# Configuration Pushover (récupérée depuis les secrets GitHub)
PUSHOVER_USER = os.getenv("PUSHOVER_USER_KEY")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_API_TOKEN")
GH_REPO = os.getenv("GH_REPO")
GH_TOKEN = os.getenv("GH_TOKEN")

def send_pushover(title, message):
    url = "https://api.pushover.net/1/messages.json"
    data = {"token": PUSHOVER_TOKEN, "user": PUSHOVER_USER, "title": title, "message": message, "priority": 1}
    requests.post(url, data=data, timeout=10)

def check_portfolio():
    # Charger les données depuis le CSV sur GitHub
    url = f"https://raw.githubusercontent.com/{GH_REPO}/main/portefeuille_data.csv"
    try:
        df = pd.read_csv(url)
    except:
        return

    alertes = []
    for _, row in df.iterrows():
        try:
            ticker = yf.Ticker(row['Ticker'])
            price = ticker.history(period="1d")['Close'].iloc[-1]
            pru = float(row['PRU'])
            sb = float(row['Seuil_Bas']) if float(row['Seuil_Bas']) > 0 else pru * 0.7
            sh = float(row.get('Seuil_Haut', 0))

            if price < sb:
                alertes.append(f"⚠️ {row['Nom']} ({row['Ticker']}) est à {price:.2f}€ | Seuil Bas: {sb:.2f}€")
            elif sh > 0 and price > sh:
                alertes.append(f"🚀 {row['Nom']} ({row['Ticker']}) est à {price:.2f}€ | Objectif: {sh:.2f}€")
        except:
            continue

    if alertes:
        send_pushover("Alerte Bourse Directe", "\n".join(alertes))

if __name__ == "__main__":
    check_portfolio()
