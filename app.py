
import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import plotly.graph_objects as go
from datetime import datetime

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
def tracer_graphique(ticker, periode, titre):
    try:
        data = yf.download(ticker, period=periode, interval="1h" if periode == "1d" else "1d", progress=False)
        if not data.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=data.index, y=data['Close'], mode='lines', line=dict(color='#00ff00' if data['Close'].iloc[-1] > data['Close'].iloc[0] else '#ff0000')))
            fig.update_layout(title=titre, height=300, margin=dict(l=0, r=0, t=30, b=0), template="plotly_dark")
            return fig
    except: return None
    return None

# --- 4. NAVIGATION ---
menu = st.tabs(["📊 Portefeuille", "📈 Graphes"])

# --- 5. CALCULS GLOBAUX ---
if st.session_state.mon_portefeuille:
    total_actuel, total_achat, var_jour_euros = 0, 0, 0
    donnees_pos = []

    for act in st.session_state.mon_portefeuille:
        try:
            t = yf.Ticker(act['Ticker'])
            hist = t.history(period="2d") # On prend 2 jours pour avoir la clôture veille
            if not hist.empty:
                prix_actuel = hist['Close'].iloc[-1]
                prix_veille = hist['Close'].iloc[-2] if len(hist) > 1 else prix_actuel
                
                val_act = prix_actuel * act['Qté']
                val_ach = act['PRU'] * act['Qté']
                
                # Variation du jour
                var_jour_euros += (prix_actuel - prix_veille) * act['Qté']
                total_actuel += val_act
                total_achat += val_ach
                
                donnees_pos.append({"act": act, "prix": prix_actuel, "val_act": val_act, "var_j": (prix_actuel - prix_veille)})
        except:
            donnees_pos.append({"act": act, "prix": 0, "val_act": 0, "var_j": 0})

    # --- ONGLET 1 : PORTEFEUILLE ---
    with menu[0]:
        # KPI Résumé
        pv_g_e = total_actuel - total_achat
        pv_g_p = (pv_g_e / total_achat * 100) if total_achat > 0 else 0
        var_j_p = (var_jour_euros / (total_actuel - var_jour_euros) * 100) if (total_actuel - var_jour_euros) > 0 else 0

        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        c_m2.metric("P/L GLOBAL", f"{pv_g_e:.2f} €", delta=f"{pv_g_p:+.2f} %")
        c_m3.metric("VAR. JOUR (9h-17h30)", f"{var_jour_euros:+.2f} €", delta=f"{var_j_p:+.2f} %")
        
        st.divider()

        for i, item in enumerate(donnees_pos):
            act, prix, val_act = item['act'], item['prix'], item['val_act']
            pv_e = (prix - act['PRU']) * act['Qté']
            color = "🟢" if pv_e >= 0 else "🔴"
            header = f"{color} {act['Nom']} | {prix:.2f}€ | {pv_e:+.2f}€"
            
            with st.expander(header):
                c1, c2, c3, c4 = st.columns(4)
                c1.write(f"**Qté:** {act['Qté']}")
                c2.write(f"**Part:** {(val_act/total_actuel*100):.2f}%")
                c3.write(f"**Var. J:** {item['var_j']:+.2f}€")
                if c4.button("🗑️", key=f"del_{i}"):
                    st.session_state.mon_portefeuille.pop(i)
                    sauvegarder_donnees(st.session_state.mon_portefeuille)
                    st.rerun()

    # --- ONGLET 2 : GRAPHES ---
    with menu[1]:
        st.subheader("Analyse Graphique")
        choix_action = st.selectbox("Choisir une action à analyser :", [a['Nom'] for a in st.session_state.mon_portefeuille])
        ticker_select = next(a['Ticker'] for a in st.session_state.mon_portefeuille if a['Nom'] == choix_action)
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.plotly_chart(tracer_graphique(ticker_select, "1d", "Journée (1D)"), use_container_width=True)
            st.plotly_chart(tracer_graphique(ticker_select, "1mo", "Mensuel (1M)"), use_container_width=True)
            st.plotly_chart(tracer_graphique(ticker_select, "max", "Depuis l'origine"), use_container_width=True)
        with col_g2:
            st.plotly_chart(tracer_graphique(ticker_select, "5d", "Hebdomadaire (5D)"), use_container_width=True)
            st.plotly_chart(tracer_graphique(ticker_select, "1y", "Annuel (1Y)"), use_container_width=True)

# --- 6. SIDEBAR (AJOUT & IMPORT) ---
with st.sidebar:
    st.header("⚙️ Paramètres")
    # Zone Import/Export ici pour gagner de la place en haut
    if st.session_state.mon_portefeuille:
        df_export = pd.DataFrame(st.session_state.mon_portefeuille)
        st.download_button(label="📥 Backup CSV", data=df_export.to_csv(index=False).encode('utf-8'), file_name='backup.csv', use_container_width=True)
    
    up = st.file_uploader("📤 Restaurer", type="csv")
    if up:
        st.session_state.mon_portefeuille = pd.read_csv(up).to_dict('records')
        sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()
    
    st.divider()
    # Formulaire d'ajout
    query = st.text_input("Rechercher Nom/ISIN")
    # ... (reste du code de recherche identique)
