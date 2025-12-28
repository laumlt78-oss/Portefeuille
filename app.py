import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import base64
import plotly.graph_objects as go
from datetime import date, datetime
from requests.exceptions import RequestException

# --- 1. CONFIGURATION SECRETS ---
try:
    USER_KEY = st.secrets["PUSHOVER_USER_KEY"]
    API_TOKEN = st.secrets["PUSHOVER_API_TOKEN"]
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
except Exception:
    st.error("Erreur : Les Secrets (Pushover ou GitHub) ne sont pas configurés sur Streamlit Cloud.")
    st.stop()

st.set_page_config(page_title="Portefeuille Persistant", layout="wide")

# --- 2. FONCTIONS GITHUB (POUR LA PERSISTENCE) ---
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
    
    # Récupérer le SHA (obligatoire pour mettre à jour un fichier existant)
    r_get = requests.get(url, headers=HEADERS_GH, timeout=10)
    sha = r_get.json()['sha'] if r_get.status_code == 200 else None
    
    payload = {
        "message": f"Sync Portefeuille {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "content": base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
    }
    if sha: payload["sha"] = sha
    
    requests.put(url, headers=HEADERS_GH, json=payload, timeout=10)

# Initialisation des données
if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_depuis_github()

# --- 3. LOGIQUE GRAPHIQUE AMÉLIORÉE ---
def tracer_graphe_depuis_achat(ticker, date_achat_str, nom):
    try:
        start_date = datetime.strptime(date_achat_str, '%Y-%m-%d')
        data = yf.download(ticker, start=start_date, progress=False)
        if not data.empty:
            fig = go.Figure(go.Scatter(x=data.index, y=data['Close'], line=dict(color='#00FF00')))
            fig.update_layout(
                title=f"Cours de {nom} depuis l'achat",
                template="plotly_dark",
                xaxis=dict(tickformat="%d %b %y"),
                yaxis=dict(side="right")
            )
            st.plotly_chart(fig, use_container_width=True)
    except: st.warning("Données graphiques non disponibles.")

# --- 4. AFFICHAGE ET NAVIGATION ---
tab_p, tab_g = st.tabs(["📊 Portefeuille", "📈 Graphes"])

# --- CALCULS ---
total_actuel, total_achat, var_jour = 0.0, 0.0, 0.0
donnees_pos = []

for i, act in enumerate(st.session_state.mon_portefeuille):
    try:
        t = yf.Ticker(act['Ticker'])
        h = t.history(period="2d")
        if not h.empty:
            p_act = h['Close'].iloc[-1]
            p_prev = h['Close'].iloc[-2] if len(h) > 1 else p_act
            v_act = p_act * float(act['Qté'])
            total_actuel += v_act
            total_achat += (float(act['PRU']) * int(act['Qté']))
            var_jour += (p_act - p_prev) * int(act['Qté'])
            donnees_pos.append({"idx": i, "act": act, "prix": p_act, "val": v_act})
    except: pass

with tab_p:
    if total_achat > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        c2.metric("P/L GLOBAL", f"{total_actuel-total_achat:.2f} €", delta=f"{((total_actuel-total_achat)/total_achat*100):+.2f} %")
        c3.metric("VAR. JOUR", f"{var_jour:+.2f} €")
        st.divider()

    for item in donnees_pos:
        idx, a, p = item['idx'], item['act'], item['prix']
        val_l = item['val']
        pv_l = (p - float(a['PRU'])) * int(a['Qté'])
        pv_p = (pv_l / (float(a['PRU']) * int(a['Qté'])) * 100) if float(a['PRU']) > 0 else 0
        poids = (val_l / total_actuel * 100) if total_actuel > 0 else 0
        
        header = f"{'🟢' if pv_l >= 0 else '🔴'} {a['Nom']} | {p:.2f}€ | {pv_l:+.2f}€ ({pv_p:+.2f}%) | {a.get('ISIN','')}"
        with st.expander(header):
            c_i1, c_i2, c_i3 = st.columns(3)
            c_i1.write(f"**Quantité :** {a['Qté']} | **PRU :** {a['PRU']}€")
            c_i1.write(f"**Poids :** {poids:.2f}%")
            c_i2.write(f"**Valeur :** {val_l:.2f}€")
            c_i2.write(f"**P/L :** {pv_l:+.2f}€")
            c_i3.write(f"**ISIN :** {a.get('ISIN')}")
            c_i3.write(f"**Achat :** {a.get('Date_Achat')}")
            
            if st.button("🗑️ Supprimer", key=f"del_{idx}"):
                st.session_state.mon_portefeuille.pop(idx)
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()

with tab_g:
    if st.session_state.mon_portefeuille:
        choix = st.selectbox("Action :", [x['Nom'] for x in st.session_state.mon_portefeuille])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        tracer_graphe_depuis_achat(info['Ticker'], info['Date_Achat'], info['Nom'])

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("🔍 Ajouter un Titre")
    with st.form("add_f", clear_on_submit=True):
        f_n = st.text_input("Nom")
        f_isin = st.text_input("ISIN")
        f_t = st.text_input("Ticker (ex: AI.PA)")
        f_p = st.number_input("PRU", min_value=0.0)
        f_q = st.number_input("Quantité", min_value=1)
        f_d = st.date_input("Date d'achat", value=date.today())
        if st.form_submit_button("Ajouter"):
            st.session_state.mon_portefeuille.append({
                "Nom": f_n, "ISIN": f_isin, "Ticker": f_t.upper(), 
                "PRU": f_p, "Qté": f_q, "Date_Achat": str(f_d)
            })
            sauvegarder_vers_github(st.session_state.mon_portefeuille)
            st.rerun()

    st.divider()
    if st.button("💾 Sauvegarder sur GitHub"):
        sauvegarder_vers_github(st.session_state.mon_portefeuille)
        st.success("Enregistré !")

    dt_str = datetime.now().strftime("%Y%m%d_%H%M")
    st.download_button(f"📥 Backup PC ({dt_str})", pd.DataFrame(st.session_state.mon_portefeuille).to_csv(index=False), f"portefeuille_{dt_str}.csv")
