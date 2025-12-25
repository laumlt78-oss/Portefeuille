import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# --- CONFIGURATION PUSHOVER ---
PUSHOVER_USER_KEY = "VOTRE_USER_KEY"
PUSHOVER_API_TOKEN = "VOTRE_API_TOKEN"

def envoyer_alerte(message):
    if PUSHOVER_USER_KEY != "VOTRE_USER_KEY": # Évite d'envoyer si non configuré
        payload = {"token": PUSHOVER_API_TOKEN, "user": PUSHOVER_USER_KEY, "message": message}
        requests.post("https://api.pushover.net/1/messages.json", data=payload)

st.set_page_config(page_title="Mon Portefeuille Pro", layout="wide")
st.title("📈 Mon Portefeuille (Marché Fermé Inclus)")

# --- DONNÉES ---
data_portefeuille = [
    {"Nom": "LVMH", "Ticker": "MC.PA", "PRU": 700.0, "Qté": 5, "Seuil_Haut": 900.0},
    {"Nom": "Apple", "Ticker": "AAPL", "PRU": 150.0, "Qté": 10, "Seuil_Haut": 220.0}
]

lignes_finales = []

for action in data_portefeuille:
    ticker_name = action['Ticker']
    # On récupère les données historiques des 5 derniers jours pour être sûr d'avoir un prix
    info_action = yf.Ticker(ticker_name)
    historique = info_action.history(period="5d")
    
    if not historique.empty:
        # On prend le prix le plus récent disponible
        prix_actuel = historique['Close'].iloc[-1]
        prix_veille = historique['Close'].iloc[-2] if len(historique) > 1 else prix_actuel
        
        # Calculs
        variation_journaliere = ((prix_actuel / prix_veille) - 1) * 100
        valorisation = prix_actuel * action['Qté']
        seuil_bas = action['PRU'] * 0.80
        performance_totale = ((prix_actuel / action['PRU']) - 1) * 100
        
        # Logique d'alerte (seulement si variation brutale)
        if variation_journaliere <= -5:
            envoyer_alerte(f"⚠️ CHUTE : {action['Nom']} ({variation_journaliere:.2f}%)")

        lignes_finales.append({
            "Nom": action['Nom'],
            "Prix Actuel": f"{prix_actuel:.2f} €",
            "Var. Jour": f"{variation_journaliere:.2f}%",
            "Valorisation": f"{valorisation:.2f} €",
            "Perf. Totale": f"{performance_totale:.2f}%",
            "Seuil Bas (-20%)": f"{seuil_bas:.2f} €",
            "Seuil Haut": f"{action['Seuil_Haut']:.2f} €"
        })
    else:
        st.error(f"Impossible de récupérer les données pour {ticker_name}")

# Affichage
if lignes_finales:
    df_final = pd.DataFrame(lignes_finales)
    st.table(df_final)
