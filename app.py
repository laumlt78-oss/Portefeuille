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
    # On télécharge un peu plus de données (1 jour complet) pour être sûr d'avoir un prix
    flux = yf.download(tickers_liste, period="1d", interval="1m")['Close']
    
    lignes_finales = []

    for _, row in df_p.iterrows():
        ticker = row['Ticker']
        
        # Sécurité : on vérifie si le ticker existe dans les données reçues
        if ticker in flux.columns:
            serie_prix = flux[ticker].dropna() # On enlève les cases vides
            
            if not serie_prix.empty:
                prix_actuel = serie_prix.iloc[-1]
                # On compare avec le prix d'il y a environ 60 minutes (si disponible)
                prix_precedent = serie_prix.iloc[0] if len(serie_prix) > 60 else serie_prix.iloc[0]
                
                # 1. CALCUL DE LA CHUTE RAPIDE
                variation_1h = ((prix_actuel / prix_precedent) - 1) * 100
                if variation_1h <= -5:
                    envoyer_alerte(f"⚠️ CHUTE : {row['Nom']} ({variation_1h:.2f}%)")

                # 2. CALCULS AUTOMATIQUES
                valorisation = prix_actuel * row['Qté']
                seuil_bas = row['PRU'] * 0.80
                performance = ((prix_actuel / row['PRU']) - 1) * 100

                # 3. ALERTE SEUILS
                if prix_actuel <= seuil_bas:
                    envoyer_alerte(f"🚨 SEUIL BAS : {row['Nom']} à {prix_actuel:.2f}€")
                elif prix_actuel >= row['Seuil_Haut']:
                    envoyer_alerte(f"💰 SEUIL HAUT : {row['Nom']} à {prix_actuel:.2f}€")

                lignes_finales.append({
                    "Nom": row['Nom'],
                    "Prix Actuel": round(float(prix_actuel), 2),
                    "Variation": f"{variation_1h:.2f}%",
                    "Valorisation": round(float(valorisation), 2),
                    "Perf Total": f"{performance:.2f}%",
                    "Seuil Bas (-20%)": round(float(seuil_bas), 2),
                    "Seuil Haut": row['Seuil_Haut']
                })

    # Affichage du tableau

    st.table(pd.DataFrame(lignes_finales))
