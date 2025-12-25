import streamlit as st
import yfinance as yf
import pandas as pd
import os

# --- CONFIGURATION PUSHOVER ---
# Remplacez par vos vrais codes entre les guillemets
USER_KEY = "VOTRE_USER_KEY"
API_TOKEN = "VOTRE_API_TOKEN"

def envoyer_alerte(message):
    if USER_KEY != "VOTRE_USER_KEY":
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": API_TOKEN,
            "user": USER_KEY,
            "message": message
        })
st.set_page_config(page_title="Mon Portefeuille", layout="wide")

# --- FONCTION POUR SAUVEGARDER LES DONNÉES ---
# On crée un petit fichier sur le serveur pour ne pas perdre vos actions
FICHIER_DATA = "portefeuille_data.csv"

def charger_donnees():
    if os.path.exists(FICHIER_DATA):
        return pd.read_csv(FICHIER_DATA).to_dict('records')
    return []

def sauvegarder_donnees(liste_actions):
    pd.DataFrame(liste_actions).to_csv(FICHIER_DATA, index=False)

# Initialisation
if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_donnees()

st.title("📈 Mon Portefeuille Boursier")

# --- FORMULAIRE DE SAISIE (BARRE LATÉRALE) ---
with st.sidebar:
    st.header("➕ Ajouter une Action")
    with st.form("ajout"):
        nom = st.text_input("Nom de l'action", "Total")
        ticker = st.text_input("Ticker (ex: TTE.PA, AAPL)", "TTE.PA")
        pru = st.number_input("Prix de revient (PRU)", value=50.0)
        qte = st.number_input("Quantité", value=10)
        seuil_haut = st.number_input("Seuil haut (Vente)", value=70.0)
        
        if st.form_submit_button("Enregistrer"):
            nouvelle = {"Nom": nom, "Ticker": ticker.upper(), "PRU": pru, "Qté": qte, "Seuil_Haut": seuil_haut}
            st.session_state.mon_portefeuille.append(nouvelle)
            sauvegarder_donnees(st.session_state.mon_portefeuille)
            st.rerun()

# --- AFFICHAGE DU TABLEAU ---
if st.session_state.mon_portefeuille:
    lignes = []
    for act in st.session_state.mon_portefeuille:
        # Récupération du prix (5 derniers jours pour éviter les erreurs de week-end)
        df_tick = yf.Ticker(act['Ticker']).history(period="5d")
        if not df_tick.empty:
            prix = df_tick['Close'].iloc[-1]
            val_totale = prix * act['Qté']
            perf = ((prix / act['PRU']) - 1) * 100
            s_bas = act['PRU'] * 0.80 # Seuil bas auto à -20%
            
            lignes.append({
                "Action": act['Nom'],
                "Ticker": act['Ticker'],
                "Prix": f"{prix:.2f}€",
                "PRU": f"{act['PRU']:.2f}€",
                "Qté": act['Qté'],
                "Valorisation": f"{val_totale:.2f}€",
                "Perf %": f"{perf:.2f}%",
                "Seuil Bas (-20%)": f"{s_bas:.2f}€",
                "Seuil Haut": f"{act['Seuil_Haut']:.2f}€"
            })

    st.subheader("Mes Positions Actuelles")
    st.table(pd.DataFrame(lignes))
# LOGIQUE D'ALERTE AUTOMATIQUE
            if prix <= s_bas:
                envoyer_alerte(f"🚨 ALERTE : {act['Nom']} a touché son seuil bas à {prix:.2f}€")
            elif prix >= act['Seuil_Haut']:
                envoyer_alerte(f"💰 ALERTE : {act['Nom']} a atteint l'objectif de {act['Seuil_Haut']:.2f}€")
    if st.button("🗑️ Tout effacer"):
        st.session_state.mon_portefeuille = []
        if os.path.exists(FICHIER_DATA): os.remove(FICHIER_DATA)
        st.rerun()
else:
    st.info("Votre portefeuille est vide. Ajoutez une action via le menu à gauche.")

