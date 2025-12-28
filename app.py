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
        sauvegarder_vers_github(st.session_state.mon_portefeuille)
        st.rerun()

# --- 4. MOTEUR DE GRAPHIQUES ---
def tracer_courbe(df, titre, pru=None):
    if df is None or df.empty:
        st.warning("Données indisponibles.")
        return
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    df = df.dropna(subset=['Close'])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'].round(2), mode='lines', line=dict(color='#00FF00', width=1.5),
        hovertemplate="<b>Date</b>: %{x|%d/%m/%y}<br><b>Prix</b>: %{y:.2f} €<extra></extra>"))
    if pru:
        fig.add_hline(y=float(pru), line_dash="dash", line_color="orange", annotation_text=f"PRU: {pru:.2f}€")
    fig.update_layout(template="plotly_dark", hovermode="x unified",
        xaxis=dict(tickformat="%d/%m/%y", tickangle=-45, nticks=20, showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
        yaxis=dict(side="right", tickformat=".2f", ticksuffix=" €", showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
        height=500, margin=dict(l=10, r=50, t=50, b=80))
    st.plotly_chart(fig, use_container_width=True)

# --- 5. AFFICHAGE DES ONGLETS ---
tab_p, tab_g, tab_h = st.tabs(["📊 Portefeuille", "📈 Graphiques Actions", "🌍 Graphe Portefeuille"])

donnees_pos = []
total_actuel, total_achat = 0.0, 0.0

# On pré-calcule les données pour éviter de bloquer l'affichage des onglets
if st.session_state.mon_portefeuille:
    for i, act in enumerate(st.session_state.mon_portefeuille):
        try:
            t = yf.Ticker(act['Ticker'])
            h = t.history(period="1d")
            if not h.empty:
                if isinstance(h.columns, pd.MultiIndex): h.columns = h.columns.get_level_values(0)
                p_act = h['Close'].iloc[-1]
                total_actuel += (p_act * float(act['Qté']))
                total_achat += (float(act['PRU']) * float(act['Qté']))
                donnees_pos.append({"idx": i, "act": act, "prix": p_act, "val": p_act * float(act['Qté'])})
        except:
            continue

with tab_p:
    if total_achat > 0:
        c1, c2 = st.columns(2)
        c1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        pl = total_actuel - total_achat
        c2.metric("P/L GLOBAL", f"{pl:.2f} €", delta=f"{(pl/total_achat*100):+.2f} %")
    
    for item in donnees_pos:
        a, idx = item['act'], item['idx']
        with st.expander(f"📌 {a['Nom']} ({a['Ticker']})"):
            col1, col2, col3 = st.columns(3)
            col1.write(f"**ISIN :** {a.get('ISIN')}")
            col1.write(f"**PRU :** {a.get('PRU')} €")
            col1.write(f"**Qté :** {a.get('Qté')}")
            col2.write(f"**Achat :** {a.get('Date_Achat')}")
            col2.write(f"**Objectif :** {a.get('Objectif')} €")
            col2.write(f"**Valeur :** {item['val']:.2f} €")
            col3.write(f"**Seuil Haut :** {a.get('Seuil_Haut')} €")
            col3.write(f"**Seuil Bas :** {a.get('Seuil_Bas')} €")
            if st.button("Supprimer", key=f"btn_{idx}"):
                st.session_state.mon_portefeuille.pop(idx)
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()

with tab_g:
    if st.session_state.mon_portefeuille:
        choix = st.selectbox("Action :", [x['Nom'] for x in st.session_state.mon_portefeuille])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        tx1, tx2, tx3 = st.tabs(["Depuis l'achat", "Mois", "Journée"])
        with tx1:
            df = yf.download(info['Ticker'], start=info['Date_Achat'], progress=False)
            tracer_courbe(df, f"Historique {info['Nom']}", pru=info['PRU'])
        with tx2:
            df = yf.download(info['Ticker'], start=datetime.now()-timedelta(days=30), progress=False)
            tracer_courbe(df, "Dernier Mois", pru=info['PRU'])
        with tx3:
            df = yf.download(info['Ticker'], period="1d", interval="5m", progress=False)
            tracer_courbe(df, "Séance du jour", pru=info['PRU'])

with tab_h:
    st.subheader("Performance du Portefeuille Global")
    tickers_list = [x['Ticker'] for x in st.session_state.mon_portefeuille]
    if tickers_list:
        h1, h2 = st.tabs(["Dernière Semaine", "Journée"])
        with h1:
            data = yf.download(tickers_list, period="7d", progress=False
