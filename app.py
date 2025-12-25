import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests

# --- 1. CONFIGURATION PUSHOVER ---
# Collez vos codes ici entre les guillemets
USER_KEY = "uy24daw7gs19ivfhwh7wgsy8amajc8"
API_TOKEN = "a2d5he9d9idw5e4rkoapym7kwfs9ha"

def envoyer_alerte(message):
    if USER_KEY != "uy24daw7gs19ivfhwh7wgsy8amajc8":
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": API_TOKEN,
            "user": USER_KEY,
            "message": message
        })

st.set_page_config(page_title="Mon Portefeuille Pro", layout="wide")

# --- 2. GESTION DES DONNÉES ---
FICHIER_DATA = "portefeuille_data.csv"

def charger_donnees():
    if os.path.exists(FICHIER_DATA):
        return pd.read_csv(FICHIER_DATA).to_dict('records')
    return []

def sauvegarder_donnees(liste_actions):
    pd.DataFrame(liste_actions).to_csv(FICHIER_DATA, index=False)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_donnees()

st.title("📊 Gestionnaire Boursier Intelligent")

# --- 3. FORMULAIRE (Sidebar) ---
with st.sidebar:
    st.header("➕ Paramètres")
    with st.form("ajout"):
        nom = st.text_input("Nom de l'action", "LVMH")
        ticker = st.text_input("Ticker (ex: MC.PA, TSLA)", "MC.PA")
        isin = st.text_input("Code ISIN", "FR0000121014")
        pru = st.number_input("Prix de revient (PRU)", value=0.0)
        qte = st.number_input("Quantité", value=1)
        s_haut = st.number_input("Seuil haut (Revente)", value=0.0)
        
        if st.form_submit_button("Enregistrer l'action"):
            nouvelle = {
                "Nom": nom, "Ticker": ticker.upper(), "ISIN": isin, 
                "PRU": pru, "Qté": qte, "Seuil_Haut": s_haut
            }
            st.session_state.mon_portefeuille.append(nouvelle)
            sauvegarder_donnees(st.session_state.mon_portefeuille)
            st.rerun()

# --- 4. CALCULS ET AFFICHAGE ---
if st.session_state.mon_portefeuille:
    lignes = []
    total_portefeuille = 0
    
    for act in st.session_state.mon_portefeuille:
        tick = yf.Ticker(act['Ticker'])
        df_tick = tick.history(period="5d")
        
        if not df_tick.empty:
            prix = df_tick['Close'].iloc[-1]
            prix_precedent = df_tick['Close'].iloc[-2] if len(df_tick) > 1 else prix
            
            # Calculs
            val_totale = prix * act['Qté']
            total_portefeuille += val_totale
            perf_pct = ((prix / act['PRU']) - 1) * 100 if act['PRU'] > 0 else 0
            plus_value = (prix - act['PRU']) * act['Qté']
            s_bas = act['PRU'] * 0.80 # Seuil bas auto à -20%
            chute_brutale = ((prix / prix_precedent) - 1) * 100
            
            # ALERTES PUSHOVER
            if chute_brutale <= -5:
                envoyer_alerte(f"⚠️ CHUTE BRUTALE : {act['Nom']} perd {chute_brutale:.2f}% !")
            if prix <= s_bas:
                envoyer_alerte(f"🚨 SEUIL BAS : {act['Nom']} est à {prix:.2f}€ (PRU -20%)")
            if s_haut > 0 and prix >= s_haut:
                envoyer_alerte(f"💰 SEUIL HAUT : {act['Nom']} est à {prix:.2f}€")

            lignes.append({
                "ISIN": act['ISIN'],
                "Nom": act['Nom'],
                "Prix": f"{prix:.2f}€",
                "PRU": f"{act['PRU']:.2f}€",
                "Qté": act['Qté'],
                "Valorisation": round(val_totale, 2),
                "+/- Value": f"{plus_value:.2f}€",
                "% Perf": f"{perf_pct:.2f}%",
                "Seuil Bas (-20%)": f"{s_bas:.2f}€",
                "Seuil Haut": f"{s_haut:.2f}€"
            })

    # Calcul du % du portefeuille
    df_final = pd.DataFrame(lignes)
    df_final["% Portefeuille"] = (df_final["Valorisation"] / total_portefeuille * 100).map("{:.2f}%".format)
    
    st.metric("Valeur Totale", f"{total_portefeuille:.2f} €")
    st.table(df_final)

    # --- 5. ACTUALITÉS ---
    st.header("📰 Dernières Actualités")
    for act in st.session_state.mon_portefeuille[:3]: # News pour les 3 premières actions
        tick = yf.Ticker(act['Ticker'])
        news = tick.news
        if news:
            st.write(f"**{act['Nom']} :** {news[0]['title']}")
            st.caption(f"Source: {news[0]['publisher']} - [Lien]({news[0]['link']})")

    if st.button("🗑️ Réinitialiser"):
        st.session_state.mon_portefeuille = []
        if os.path.exists(FICHIER_DATA): os.remove(FICHIER_DATA)
        st.rerun()
