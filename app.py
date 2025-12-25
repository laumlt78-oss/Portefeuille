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
                "token": API_TOKEN,
                "user": USER_KEY,
                "message": message
            }, timeout=5)
        except:
            pass

st.set_page_config(page_title="Mon Portefeuille Pro", layout="wide")

# --- 2. GESTION DES DONNÉES (VERSION ANTI-ERREUR) ---
FICHIER_DATA = "portefeuille_data.csv"

def charger_donnees():
    if not os.path.exists(FICHIER_DATA):
        return []
    try:
        # Si le fichier est vide (0 octet), on le supprime et on renvoie vide
        if os.path.getsize(FICHIER_DATA) == 0:
            os.remove(FICHIER_DATA)
            return []
        df = pd.read_csv(FICHIER_DATA)
        return df.to_dict('records')
    except Exception:
        return []

def sauvegarder_donnees(liste_actions):
    if not liste_actions:
        if os.path.exists(FICHIER_DATA):
            os.remove(FICHIER_DATA)
    else:
        df = pd.DataFrame(liste_actions)
        df.to_csv(FICHIER_DATA, index=False)

# Initialisation de la session
if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_donnees()

st.title("🚀 Mon Assistant Boursier Personnel")

# --- 3. RECHERCHE ET AJOUT (SIDEBAR) ---
with st.sidebar:
    st.header("🔍 Trouver une Action")
    recherche = st.text_input("Nom de l'entreprise (ex: LVMH, Apple)")
    
    ticker_suggere = ""
    nom_suggere = ""
    
    if recherche:
        try:
            # Recherche de tickers par nom
            suggestions = yf.utils.get_tickers_by_name(recherche)
            if not suggestions.empty:
                liste_choix = suggestions.apply(lambda x: f"{x['shortname']} ({x['symbol']} - {x['exchange']})", axis=1).tolist()
                selection = st.selectbox("Résultats trouvés :", liste_choix)
                ticker_suggere = selection.split('(')[1].split(' -')[0]
                nom_suggere = selection.split(' (')[0]
        except:
            st.error("Service de recherche indisponible.")

    st.divider()
    st.header("📝 Détails de l'achat")
    with st.form("form_ajout", clear_on_submit=True):
        f_nom = st.text_input("Nom", value=nom_suggere)
        f_ticker = st.text_input("Ticker", value=ticker_suggere)
        f_pru = st.number_input("Prix d'achat (PRU)", min_value=0.0, step=0.1)
        f_qte = st.number_input("Quantité", min_value=1, step=1)
        f_haut = st.number_input("Objectif de vente (Haut)", min_value=0.0, step=0.1)
        
        if st.form_submit_button("Ajouter au Portefeuille"):
            if f_ticker:
                nouvelle_action = {
                    "Nom": f_nom,
                    "Ticker": f_ticker.upper(),
                    "PRU": f_pru,
                    "Qté": f_qte,
                    "Seuil_Haut": f_haut
                }
                st.session_state.mon_portefeuille.append(nouvelle_action)
                sauvegarder_donnees(st.session_state.mon_portefeuille)
                st.success(f"{f_nom} ajouté !")
                st.rerun()
            else:
                st.warning("Veuillez sélectionner un Ticker.")

# --- 4. AFFICHAGE DU PORTEFEUILLE ---
if st.session_state.mon_portefeuille:
    total_portefeuille = 0
    lignes_data = []

    st.subheader("📊 Mes Positions Actuelles")
    
    for i, act in enumerate(st.session_state.mon_portefeuille):
        try:
            # Récupération des données financières
            ticket_yf = yf.Ticker(act['Ticker'])
            hist = ticket_yf.history(period="5d")
            
            if not hist.empty:
                prix_actuel = hist['Close'].iloc[-1]
                prix_veille = hist['Close'].iloc[-2] if len(hist) > 1 else prix_actuel
                
                # Calculs
                valeur_ligne = prix_actuel * act['Qté']
                total_portefeuille += valeur_ligne
                perf_globale = ((prix_actuel / act['PRU']) - 1) * 100 if act['PRU'] > 0 else 0
                seuil_bas_auto = act['PRU'] * 0.80 # Alerte à -20%
                var_jour = ((prix_actuel / prix_veille) - 1) * 100

                # Envoi d'alertes Pushover
                if prix_actuel <= seuil_bas_auto:
                    envoyer_alerte(f"🚨 SEUIL BAS : {act['Nom']} est à {prix_actuel:.2f}€")
                if act['Seuil_Haut'] > 0 and prix_actuel >= act['Seuil_Haut']:
                    envoyer_alerte(f"💰 SEUIL HAUT : {act['Nom']} est à {prix_actuel:.2f}€")

                # Préparation du tableau
                lignes_data.append({
                    "ID": i,
                    "Action": act['Nom'],
                    "Ticker": act['Ticker'],
                    "Prix": f"{prix_actuel:.2f}€",
                    "Var. Jour": f"{var_jour:+.2f}%",
                    "PRU": f"{act['PRU']:.2f}€",
                    "Qté": act['Qté'],
                    "Valeur": valeur_ligne,
                    "Perf %": f"{perf_globale:+.2f}%",
                    "Seuil Bas": f"{seuil_bas_auto:.2f}€",
                    "Seuil Haut": f"{act['Seuil_Haut']:.2f}€"
                })
        except:
            st.error(f"Erreur de données pour {act['Ticker']}")

    if lignes_data:
        df_visu = pd.DataFrame(lignes_data)
        
        # Affichage du résumé
        st.metric("Valeur Totale", f"{total_portefeuille:.2f} €")
        
        # Affichage avec possibilité de supprimer
        for idx, row in df_visu.iterrows():
            with st.expander(f"📌 {row['Action']} ({row['Ticker']}) : {row['Prix']} | {row['Perf %']}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Quantité:** {row['Qté']}")
                c1.write(f"**Valeur Totale:** {row['Valeur']:.2f}€")
                c2.write(f"**Seuil Bas (-20%):** {row['Seuil Bas']}")
                c2.write(f"**Seuil Haut:** {row['Seuil Haut']}")
                if c3.button("🗑️ Supprimer cette ligne", key=f"btn_{row['ID']}"):
                    st.session_state.mon_portefeuille.pop(int(row['ID']))
                    sauvegarder_donnees(st.session_state.mon_portefeuille)
                    st.rerun()

    # --- 5. ACTUALITÉS ---
    st.divider()
    st.header("📰 News Marché")
    for act in st.session_state.mon_portefeuille[:2]:
        news = yf.Ticker(act['Ticker']).news
        if news:
            st.write(f"**{act['Nom']}** : {news[0].get('title')}")
            st.caption(f"[Lire l'article]({news[0].get('link')})")

else:
    st.info("👋 Bienvenue ! Utilisez la barre à gauche pour ajouter votre première action.")

