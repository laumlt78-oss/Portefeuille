import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import base64
import plotly.graph_objects as go
from datetime import date, datetime, timedelta

# --- 1. CONFIGURATION INTERFACE ---
st.set_page_config(
    page_title="Portefeuille Pro", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# Correction du paramètre : unsafe_allow_html
st.markdown("""
    <style>
        [data-testid="stSidebar"] { min-width: 350px; max-width: 350px; }
    </style>
    """, unsafe_allow_html=True)

try:
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
except Exception as e:
    st.error("Secrets GitHub manquants.")
    st.stop()

# --- 2. GESTION DONNÉES ---
FICHIER_DATA = "portefeuille_data.csv"
HEADERS_GH = {"Authorization": f"token {GH_TOKEN}"}

def charger_depuis_github():
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{FICHIER_DATA}"
    try:
        r = requests.get(url, headers=HEADERS_GH, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            from io import StringIO
            return pd.read_csv(StringIO(content)).to_dict('records')
    except: pass
    return []

def sauvegarder_vers_github(liste):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{FICHIER_DATA}"
    df = pd.DataFrame(liste)
    csv_content = df.to_csv(index=False)
    r_get = requests.get(url, headers=HEADERS_GH, timeout=10)
    sha = r_get.json().get('sha') if r_get.status_code == 200 else None
    payload = {"message": "Sync", "content": base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')}
    if sha: payload["sha"] = sha
    requests.put(url, headers=HEADERS_GH, json=payload, timeout=10)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_depuis_github()

# --- 3. BANDEAU DE GAUCHE (SIDEBAR) ---
with st.sidebar:
    st.title("⚙️ Gestion")
    with st.form("form_ajout", clear_on_submit=True):
        st.subheader("➕ Ajouter un titre")
        f_n = st.text_input("Nom")
        f_i = st.text_input("ISIN")
        f_t = st.text_input("Ticker (ex: MC.PA)")
        f_p = st.number_input("PRU", min_value=0.0, format="%.2f")
        f_q = st.number_input("Quantité", min_value=0.0, format="%.2f")
        f_d = st.date_input("Date d'achat")
        st.write("---")
        f_obj = st.number_input("Objectif", min_value=0.0, format="%.2f")
        f_sh = st.number_input("Seuil Haut", min_value=0.0, format="%.2f")
        f_sb = st.number_input("Seuil Bas", min_value=0.0, format="%.2f")
        if st.form_submit_button("Valider l'ajout"):
            if f_n and f_t:
                st.session_state.mon_portefeuille.append({
                    "Nom": f_n, "ISIN": f_i, "Ticker": f_t.upper(),
                    "PRU": f_p, "Qté": f_q, "Date_Achat": str(f_d),
                    "Objectif": f_obj, "Seuil_Haut": f_sh, "Seuil_Bas": f_sb
                })
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()
    st.divider()
    up = st.file_uploader("📥 Restaurer CSV", type="csv")
    if up:
        df_up = pd.read_csv(up)
        st.session_state.mon_portefeuille = df_up.to_dict('records')
        sauvegarder_
