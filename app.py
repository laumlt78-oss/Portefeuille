import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import base64
import plotly.graph_objects as go
from datetime import date, datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Portefeuille Expert", layout="wide", initial_sidebar_state="expanded")

try:
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
except:
    st.error("Secrets GitHub manquants. Vérifiez votre configuration Streamlit Cloud.")
    st.stop()

# --- 2. GESTION GITHUB ---
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

# --- 3. MOTEUR DE GRAPHIQUES ---
def tracer_courbe(df, titre, pru=None, s_h=None, s_b=None):
    if df is None or df.empty:
        st.warning("Données indisponibles pour le graphique.")
        return
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color='#00FF00', width=2), name="Cours"))
    if pru: fig.add_hline(y=float(pru), line_dash="dash", line_color="orange", annotation_text="PRU")
    if s_h and float(s_h) > 0: fig.add_hline(y=float(s_h), line_color="green", line_width=1.5, annotation_text="Objectif")
    if s_b and float(s_b) > 0: fig.add_hline(y=float(s_b), line_color="red", line_width=1.5, annotation_text="Alerte")
    fig.update_layout(template="plotly_dark", hovermode="x unified", height=500, xaxis=dict(tickformat="%d/%m/%y"), yaxis=dict(side="right"))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. CALCULS FINANCIERS SÉCURISÉS ---
positions_calculees = []
total_actuel, total_achat = 0.0, 0.0

for i, act in enumerate(st.session_state.mon_portefeuille):
    try:
        # Correction robuste des valeurs numériques (évite le nan)
        pru = float(act.get('PRU', 0)) if pd.notnull(act.get('PRU')) else 0.0
        qte = float(act.get('Qté', 0)) if pd.notnull(act.get('Qté')) else 0.0
        s_haut = float(act.get('Seuil_Haut', 0)) if pd.notnull(act.get('Seuil_Haut')) else 0.0
        
        # Calcul auto du seuil bas si absent ou égal à 0
        raw_sb = act.get('Seuil_Bas')
        if pd.isnull(raw_sb) or float(raw_sb) == 0:
            s_bas = pru * 0.7
        else:
            s_bas = float(raw_sb)

        tk = yf.Ticker(act['Ticker'])
        hist = tk.history(period="1d")
        c_act = hist['Close'].iloc[-1] if not hist.empty else 0
        
        val_titre = c_act * qte
        pv_euro = val_titre - (pru * qte)
        pv_perc = (pv_euro / (pru * qte) * 100) if (pru * qte) > 0 else 0
        
        total_actuel += val_titre
        total_achat += (pru * qte)
        
        positions_calculees.append({
            "idx": i, "act": act, "c_act": c_act, "val": val_titre, 
            "pv": pv_euro, "pc": pv_perc, "sb": s_bas, "sh": s_haut, "pru": pru, "qte": qte
        })
    except: continue

# --- 5. BARRE LATÉRALE ---
with st.sidebar:
    st.title("💰 Résumé Global")
    if total_achat > 0:
        diff = total_actuel - total_achat
        st.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        st.metric("P/L GLOBAL", f"{diff:+.2f} €", delta=f"{(diff/total_achat*100):+.2f}%")
    st.divider()
    
    with st.form("add_form", clear_on_submit=True):
        st.subheader("➕ Ajouter un titre")
        n, i, t = st.text_input("Nom"), st.text_input("ISIN"), st.text_input("Ticker")
        p, q = st.number_input("PRU", min_value=0.0), st.number_input("Qté", min_value=0.0)
        d = st.date_input("Date Achat", value=date.today())
        sh = st.number_input("Seuil Haut", min_value=0.0)
        sb = st.number_input("Seuil Bas (0=Auto)", min_value=0.0)
        if st.form_submit_button("Ajouter"):
            if n and t:
                v_sb = sb if sb > 0 else (p * 0.7)
                st.session_state.mon_portefeuille.append({
                    "Nom":n, "ISIN":i, "Ticker":t.
