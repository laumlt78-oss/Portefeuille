import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests

# --- 1. CONFIGURATION PUSHOVER ---
USER_KEY = "uy24daw7gs19ivfhwh7wgsy8amajc8"
API_TOKEN = "a2d5he9d9idw5e4rkoapym7kwfs9ha"


def envoyer_alerte(message):
    if USER_KEY != "VOTRE_USER_KEY_ICI":
        try:
            requests.post("https://api.pushover.net/1/messages.json", data={
                "token": API_TOKEN, "user": USER_KEY, "message": message
            }, timeout=5)
        except: pass

st.set_page_config(page_title="Mon Portefeuille Pro", layout="wide")

# --- 2. GESTION DES DONNÉES ---
FICHIER_DATA = "portefeuille_data.csv"

def charger_donnees():
    if not os.path.exists(FICHIER_DATA) or os.path.getsize(FICHIER_DATA) == 0:
        return []
    try:
        return pd.read_csv(FICHIER_DATA).to_dict('records')
    except:
        return []

def sauvegarder_donnees(liste_actions):
    if liste_actions:
        pd.DataFrame(liste_actions).to_csv(FICHIER_DATA, index=False)
    elif os.path.exists(FICHIER_DATA):
        os.remove(FICHIER_DATA)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_donnees()

st.title("📈 Mon Portefeuille")

# --- 3. AJOUT D'ACTION (SIDEBAR) ---
with st.sidebar:
    st.header("➕ Ajouter une Action")
    
    # Recherche facultative
    recherche = st.text_input("Rechercher par nom (ex: Total)")
    ticker_auto = ""
    
    if recherche:
        try:
            # On essaye une méthode plus simple pour les suggestions
            search = yf.Search(recherche, max_results=5)
            if search.quotes:
                choix = [f"{q['shortname']} ({q['symbol']})" for q in search.quotes]
                selection = st.selectbox("Sélectionnez l'action :", choix)
                ticker_auto = selection.split('(')[1].replace(')', '')
        except:
            st.warning("Recherche automatique indisponible. Entrez le Ticker à la main.")

    st.divider()
    
    with st.form("ajout_form", clear_on_submit=True):
        f_nom = st.text_input("Nom de l'action", value=recherche if not ticker_auto else selection.split(' (')[0])
        f_ticker = st.text_input("Ticker (ex: MC.PA, AAPL)", value=ticker_auto).upper()
        f_pru = st.number_input("Prix d'achat (PRU)", min_value=0.0)
        f_qte = st.number_input("Quantité", min_value=1)
        f_haut = st.number_input("Seuil Haut (Vente)", min_value=0.0)
        
        if st.form_submit_button("Enregistrer"):
            if f_ticker:
                st.session_state.mon_portefeuille.append({
                    "Nom": f_nom, "Ticker": f_ticker, "PRU": f_pru, "Qté": f_qte, "Seuil_Haut": f_haut
                })
                sauvegarder_donnees(st.session_state.mon_portefeuille)
                st.rerun()

# --- 4. AFFICHAGE ---
if st.session_state.mon_portefeuille:
    total_val = 0
    for i, act in enumerate(st.session_state.mon_portefeuille):
        try:
            # On demande les données
            t = yf.Ticker(act['Ticker'])
            # On utilise fast_info pour éviter les lenteurs de history()
            prix = t.fast_info['lastPrice']
            
            val = prix * act['Qté']
            total_val += val
            perf = ((prix / act['PRU']) - 1) * 100 if act['PRU'] > 0 else 0
            
            with st.expander(f"**{act['Nom']}** : {prix:.2f}€ ({perf:+.2f}%)"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"Valeur: {val:.2f}€")
                c2.write(f"PRU: {act['PRU']:.2f}€")
                if c3.button("🗑️ Supprimer", key=f"del_{i}"):
                    st.session_state.mon_portefeuille.pop(i)
                    sauvegarder_donnees(st.session_state.mon_portefeuille)
                    st.rerun()
                
                # Alertes (visuelles et Push)
                if prix <= act['PRU'] * 0.8:
                    st.error("🚨 SEUIL BAS ATTEINT (-20%)")
                    envoyer_alerte(f"Alerte Basse: {act['Nom']}")
                if act['Seuil_Haut'] > 0 and prix >= act['Seuil_Haut']:
                    st.success("💰 OBJECTIF ATTEINT !")
                    envoyer_alerte(f"Objectif atteint: {act['Nom']}")
        except:
            st.error(f"Impossible de lire le ticker: {act['Ticker']}")

    st.divider()
    st.metric("TOTAL PORTEFEUILLE", f"{total_val:.2f} €")
else:
    st.info("Utilisez le menu à gauche pour ajouter votre première action.")
