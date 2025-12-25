import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests

# --- 1. CONFIGURATION PUSHOVER ---
USER_KEY = "uy24daw7gs19ivfhwh7wgsy8amajc8"
API_TOKEN = "a2d5he9d9idw5e4rkoapym7kwfs9ha"

def envoyer_alerte(message):
    if USER_KEY != "uy24daw7gs19ivfhwh7wgsy8amajc8":
        requests.post("https://api.pushover.net/1/messages.json", data={"token": API_TOKEN, "user": USER_KEY, "message": message})

st.set_page_config(page_title="Mon Portefeuille Pro", layout="wide")

# --- 2. GESTION DES DONNÉES ---
FICHIER_DATA = "portefeuille_data.csv"

def charger_donnees():
    # On vérifie si le fichier existe ET s'il n'est pas vide (plus de 0 octet)
    if os.path.exists(FICHIER_DATA) and os.path.getsize(FICHIER_DATA) > 0:
        try:
            df = pd.read_csv(FICHIER_DATA)
            # On vérifie aussi que le dataframe n'est pas vide après lecture
            if not df.empty:
                return df.to_dict('records')
        except Exception:
            return []
    return []

def sauvegarder_donnees(liste_actions):
    if liste_actions:
        df = pd.DataFrame(liste_actions)
        df.to_csv(FICHIER_DATA, index=False)
    else:
        # Si on vide tout, on supprime le fichier pour éviter les erreurs au prochain démarrage
        if os.path.exists(FICHIER_DATA):
            os.remove(FICHIER_DATA)

# --- 3. RECHERCHE INTELLIGENTE DE TICKER ---
with st.sidebar:
    st.header("🔍 Rechercher une Action")
    recherche = st.text_input("Tapez le nom (ex: LVMH, Total, Apple)")
    ticker_choisi = ""
    nom_choisi = ""
    
    if recherche:
        # On cherche les correspondances sur Yahoo Finance
        suggestions = yf.utils.get_tickers_by_name(recherche)
        if not suggestions.empty:
            # On prépare une liste de choix lisible
            choix = suggestions.apply(lambda x: f"{x['shortname']} ({x['symbol']} - {x['exchange']})", axis=1).tolist()
            selection = st.selectbox("Choisissez l'action précise :", choix)
            # On extrait le ticker du choix sélectionné
            ticker_choisi = selection.split('(')[1].split(' -')[0]
            nom_choisi = selection.split(' (')[0]
            st.success(f"Ticker sélectionné : {ticker_choisi}")

    st.divider()
    
    # --- 4. FORMULAIRE D'AJOUT ---
    st.header("📝 Détails de la position")
    with st.form("ajout"):
        f_nom = st.text_input("Nom de l'action", value=nom_choisi)
        f_ticker = st.text_input("Ticker", value=ticker_choisi)
        f_isin = st.text_input("Code ISIN (Optionnel)")
        f_pru = st.number_input("Prix d'achat (PRU)", value=0.0)
        f_qte = st.number_input("Quantité possédée", value=1)
        f_haut = st.number_input("Objectif de vente (Seuil Haut)", value=0.0)
        
        if st.form_submit_button("Ajouter au portefeuille"):
            if f_ticker:
                nouvelle = {"Nom": f_nom, "Ticker": f_ticker.upper(), "ISIN": f_isin, "PRU": f_pru, "Qté": f_qte, "Seuil_Haut": f_haut}
                st.session_state.mon_portefeuille.append(nouvelle)
                sauvegarder_donnees(st.session_state.mon_portefeuille)
                st.rerun()
            else:
                st.error("Veuillez sélectionner un ticker.")

# --- 5. AFFICHAGE ET MODIFICATION ---
if st.session_state.mon_portefeuille:
    total_v = 0
    lignes_affichage = []
    
    st.subheader("📊 Mes Positions")
    
    # On parcourt avec l'index pour pouvoir supprimer/modifier précisément
    for i, act in enumerate(st.session_state.mon_portefeuille):
        # Récupération cours
        tick_info = yf.Ticker(act['Ticker'])
        hist = tick_info.history(period="5d")
        
        if not hist.empty:
            prix = hist['Close'].iloc[-1]
            val = prix * act['Qté']
            total_v += val
            perf = ((prix / act['PRU']) - 1) * 100 if act['PRU'] > 0 else 0
            s_bas = act['PRU'] * 0.80
            
            # Affichage en colonnes pour chaque ligne (mieux pour mobile)
            col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 2, 1])
            with col1:
                st.write(f"**{act['Nom']}**")
                st.caption(f"{act['Ticker']} | {act['ISIN']}")
            with col2:
                st.write(f"Prix: {prix:.2f}€")
                st.write(f"PRU: {act['PRU']:.2f}€")
            with col3:
                st.write(f"Val: {val:.2f}€")
                st.write(f"Perf: {perf:.2f}%")
            with col4:
                st.caption(f"Bas: {s_bas:.2f}€")
                st.caption(f"Haut: {act['Seuil_Haut']:.2f}€")
            with col5:
                # Bouton de suppression unique pour cette ligne
                if st.button("🗑️", key=f"del_{i}"):
                    st.session_state.mon_portefeuille.pop(i)
                    sauvegarder_donnees(st.session_state.mon_portefeuille)
                    st.rerun()
            st.divider()

    st.metric("Valeur Totale du Portefeuille", f"{total_v:.2f} €")
else:
    st.info("Recherchez une action dans le menu à gauche pour commencer.")



