
import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import plotly.graph_objects as go

# --- 1. CONFIGURATION PUSHOVER ---
USER_KEY = "uy24daw7gs19ivfhwh7wgsy8amajc8"
API_TOKEN = "a2d5he9d9idw5e4rkoapym7kwfs9ha"



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
    except: return []

def sauvegarder_donnees(liste_actions):
    if liste_actions:
        pd.DataFrame(liste_actions).to_csv(FICHIER_DATA, index=False)
    elif os.path.exists(FICHIER_DATA):
        os.remove(FICHIER_DATA)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_donnees()

# --- 3. FONCTION GRAPHIQUE ---
def afficher_5_graphes(ticker):
    periodes = [
        ("1d", "Aujourd'hui"),
        ("5d", "5 Jours"),
        ("1mo", "1 Mois"),
        ("1y", "1 An"),
        ("max", "Max")
    ]
    
    st.subheader(f"Analyse Historique : {ticker}")
    cols = st.columns(len(periodes))
    
    for i, (p, label) in enumerate(periodes):
        try:
            data = yf.download(ticker, period=p, interval="1h" if p == "1d" else "1d", progress=False)
            if not data.empty:
                fig = go.Figure()
                color = "green" if data['Close'].iloc[-1] >= data['Close'].iloc[0] else "red"
                fig.add_trace(go.Scatter(x=data.index, y=data['Close'], line=dict(color=color, width=2)))
                fig.update_layout(
                    title=label, height=200, margin=dict(l=0, r=0, t=30, b=0),
                    xaxis_visible=False, yaxis_visible=True, template="plotly_dark"
                )
                st.plotly_chart(fig, use_container_width=True)
        except:
            st.error(f"Erreur graphe {label}")

# --- 4. NAVIGATION PAR ONGLETS ---
tab_portefeuille, tab_graphes = st.tabs(["📊 Portefeuille", "📈 Analyse Graphes"])

# --- 5. CALCULS ---
if st.session_state.mon_portefeuille:
    total_actuel, total_achat, var_jour_euros = 0, 0, 0
    donnees_pos = []

    for act in st.session_state.mon_portefeuille:
        try:
            t = yf.Ticker(act['Ticker'])
            hist = t.history(period="2d")
            if not hist.empty:
                p_act = hist['Close'].iloc[-1]
                p_veille = hist['Close'].iloc[-2] if len(hist) > 1 else p_act
                
                total_actuel += (p_act * act['Qté'])
                total_achat += (act['PRU'] * act['Qté'])
                var_jour_euros += (p_act - p_veille) * act['Qté']
                
                donnees_pos.append({"act": act, "prix": p_act, "var_j": (p_act - p_veille)})
        except: pass

    # --- TAB 1 : VUE LISTE ---
    with tab_portefeuille:
        pv_g_e = total_actuel - total_achat
        pv_g_p = (pv_g_e / total_achat * 100) if total_achat > 0 else 0
        var_j_p = (var_jour_euros / (total_actuel - var_jour_euros) * 100) if (total_actuel - var_jour_euros) > 0 else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        c2.metric("P/L GLOBAL", f"{pv_g_e:.2f} €", delta=f"{pv_g_p:+.2f} %")
        c3.metric("VAR. JOUR", f"{var_jour_euros:+.2f} €", delta=f"{var_j_p:+.2f} %")

        st.divider()

        for i, item in enumerate(donnees_pos):
            act, prix = item['act'], item['prix']
            pv_e = (prix - act['PRU']) * act['Qté']
            color = "🟢" if pv_e >= 0 else "🔴"
            header = f"{color} {act['Nom']} | {prix:.2f}€ | {pv_e:+.2f}€"
            
            with st.expander(header):
                col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
                col1.write(f"**Qté:** {act['Qté']} | **PRU:** {act['PRU']}€")
                col2.write(f"**Var J:** {item['var_j']:+.2f}€")
                col3.write(f"**Objectif:** {act['Seuil_Haut']}€")
                if col4.button("🗑️", key=f"del_{i}"):
                    st.session_state.mon_portefeuille.pop(i)
                    sauvegarder_donnees(st.session_state.mon_portefeuille)
                    st.rerun()

    # --- TAB 2 : VUE GRAPHES ---
    with tab_graphes:
        choix = st.selectbox("Sélectionnez une ligne :", [a['Nom'] for a in st.session_state.mon_portefeuille])
        ticker_sel = next(a['Ticker'] for a in st.session_state.mon_portefeuille if a['Nom'] == choix)
        afficher_5_graphes(ticker_sel)

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("🔍 Ajouter / Paramètres")
    # Zone d'import/export
    df_exp = pd.DataFrame(st.session_state.mon_portefeuille)
    st.download_button("📥 Backup CSV", df_exp.to_csv(index=False).encode('utf-8'), "portefeuille.csv", use_container_width=True)
    
    up = st.file_uploader("📤 Restaurer", type="csv")
    if up:
        st.session_state.mon_portefeuille = pd.read_csv(up).to_dict('records')
        sauvegarder_donnees(st.session_state.mon_portefeuille)
        st.rerun()

    st.divider()
    # Recherche Nom/ISIN
    query = st.text_input("Rechercher Action/ISIN")
    # ... (Ajout classique du formulaire ici)
