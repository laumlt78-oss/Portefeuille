import streamlit as st
import yfinance as yf
import pandas as pd
import requests # Nécessaire pour envoyer l'alerte

# --- CONFIGURATION PUSHOVER ---
# Remplacez ces codes par les vôtres reçus sur Pushover.net
PUSHOVER_USER_KEY = "VOTRE_USER_KEY"
PUSHOVER_API_TOKEN = "VOTRE_API_TOKEN"

def envoyer_alerte(message):
    payload = {
        "token": PUSHOVER_API_TOKEN,
        "user": PUSHOVER_USER_KEY,
        "message": message
    }
    requests.post("https://api.pushover.net/1/messages.json", data=payload)

st.set_page_config(page_title="Mon Portefeuille Pro", layout="wide")
st.title("📈 Gestionnaire de Portefeuille & Alertes")

# --- DONNÉES DU PORTEFEUILLE ---
data_portefeuille = [
    {"Nom": "LVMH", "Ticker": "MC.PA", "PRU": 700.0, "Qté": 5, "Seuil_Haut": 900.0},
    {"Nom": "Apple", "Ticker": "AAPL", "PRU": 150.0, "Qté": 10, "Seuil_Haut": 220.0}
]

df_p = pd.DataFrame(data_portefeuille)
tickers_liste = df_p['Ticker'].tolist()

# --- RÉCUPÉRATION DES COURS ET LOGIQUE D'ALERTE ---
if tickers_liste:
    # On récupère les données des dernières 2 heures pour comparer le prix
    flux = yf.download(tickers_liste, period="2h", interval="1h")['Close']
    
    lignes_finales = []

    for _, row in df_p.iterrows():
        ticker = row['Ticker']
        # Prix actuel et prix il y a 1 heure
        prix_actuel = flux[ticker].iloc[-1]
        prix_precedent = flux[ticker].iloc[0]
        
        # 1. CALCUL DE LA CHUTE RAPIDE (5% en 1h)
        variation_1h = ((prix_actuel / prix_precedent) - 1) * 100
        if variation_1h <= -5:
            envoyer_alerte(f"⚠️ CHUTE RAPIDE : {row['Nom']} a perdu {variation_1h:.2f}% en 1h !")

        # 2. CALCULS AUTOMATIQUES
        valorisation = prix_actuel * row['Qté']
        seuil_bas = row['PRU'] * 0.80
        performance = ((prix_actuel / row['PRU']) - 1) * 100

        # 3. ALERTE SEUILS (Haut et Bas)
        if prix_actuel <= seuil_bas:
            envoyer_alerte(f"🚨 SEUIL BAS ATTEINT : {row['Nom']} est à {prix_actuel:.2f}€ (Seuil: {seuil_bas:.2f}€)")
        elif prix_actuel >= row['Seuil_Haut']:
            envoyer_alerte(f"💰 SEUIL HAUT ATTEINT : {row['Nom']} est à {prix_actuel:.2f}€")

        lignes_finales.append({
            "Nom": row['Nom'],
            "Prix Actuel": round(prix_actuel, 2),
            "Variation 1h": f"{variation_1h:.2f}%",
            "Valorisation": round(valorisation, 2),
            "Perf Total": f"{performance:.2f}%",
            "Seuil Bas (-20%)": round(seuil_bas, 2),
            "Seuil Haut": row['Seuil_Haut']
        })

    # Affichage du tableau
    st.table(pd.DataFrame(lignes_finales))