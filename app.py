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
    # Optionnel pour l'app, mais nécessaire pour le bouton de test
    P_USER = st.secrets.get("PUSHOVER_USER_KEY")
    P_TOKEN = st.secrets.get("PUSHOVER_API_TOKEN")
except:
    st.error("Secrets manquants dans Streamlit Cloud.")
    st.stop()

# --- 2. FONCTIONS DE COMMUNICATION ---
def envoyer_test_pushover():
    if not P_USER or not P_TOKEN:
        st.sidebar.error("Clés Pushover manquantes dans les secrets.")
        return
    url = "https://api.pushover.net/1/messages.json"
    data = {
        "token": P_TOKEN,
        "user": P_USER,
        "title": "Test Portefeuille",
        "message": "✅ La connexion entre Streamlit et votre téléphone fonctionne !",
        "priority": 0
    }
    try:
        r = requests.post(url, data=data, timeout=10)
        if r.status_code == 200: st.sidebar.success("Notification envoyée !")
        else: st.sidebar.error(f"Erreur Pushover : {r.status_code}")
    except Exception as e:
        st.sidebar.error(f"Erreur : {e}")

def charger_depuis_github():
    url = f"https://api.github.com/repos/{GH_REPO}/contents/portefeuille_data.csv"
    try:
        r = requests.get(url, headers={"Authorization": f"token {GH_TOKEN}"}, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            from io import StringIO
            return pd.read_csv(StringIO(content)).to_dict('records')
    except: pass
    return []

def sauvegarder_vers_github(liste):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/portefeuille_data.csv"
    df = pd.DataFrame(liste)
    csv_content = df.to_csv(index=False)
    r_get = requests.get(url, headers={"Authorization": f"token {GH_TOKEN}"}, timeout=10)
    sha = r_get.json().get('sha') if r_get.status_code == 200 else None
    payload = {"message": "Sync", "content": base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')}
    if sha: payload["sha"] = sha
    requests.put(url, headers={"Authorization": f"token {GH_TOKEN}"}, json=payload, timeout=10)

# Initialisation
if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_depuis_github()

# --- 3. CALCULS ---
positions_calculees = []
total_actuel, total_achat = 0.0, 0.0

for i, act in enumerate(st.session_state.mon_portefeuille):
    try:
        pru = float(act.get('PRU', 0)) if pd.notnull(act.get('PRU')) else 0.0
        qte = float(act.get('Qté', 0)) if pd.notnull(act.get('Qté')) else 0.0
        sb_val = act.get('Seuil_Bas')
        s_bas = float(sb_val) if pd.notnull(sb_val) and float(sb_val) > 0 else pru * 0.7
        
        tk = yf.Ticker(act['Ticker'])
        c_act = tk.history(period="1d")['Close'].iloc[-1]
        val_titre = c_act * qte
        total_actuel += val_titre
        total_achat += (pru * qte)
        
        positions_calculees.append({
            "idx": i, "act": act, "c_act": c_act, "val": val_titre, 
            "pv": val_titre - (pru * qte), "sb": s_bas, "pru": pru, "qte": qte
        })
    except: continue

# --- 4. INTERFACE ---
with st.sidebar:
    st.title("💰 Résumé Global")
    if total_achat > 0:
        st.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        st.metric("P/L GLOBAL", f"{total_actuel-total_achat:+.2f} €", delta=f"{((total_actuel-total_achat)/total_achat*100):+.2f}%")
    st.divider()
    
    # Formulaire d'ajout
    with st.form("add_form", clear_on_submit=True):
        st.subheader("➕ Ajouter un titre")
        n, i, t = st.text_input("Nom"), st.text_input("ISIN"), st.text_input("Ticker")
        p, q = st.number_input("PRU", min_value=0.0), st.number_input("Qté", min_value=0.0)
        d = st.date_input("Date Achat", value=date.today())
        if st.form_submit_button("Ajouter"):
            if n and t:
                st.session_state.mon_portefeuille.append({"Nom":n, "ISIN":i, "Ticker":t.upper(), "PRU":p, "Qté":q, "Date_Achat":str(d), "Seuil_Haut":0, "Seuil_Bas":p*0.7})
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()
    
    st.divider()
    if st.button("🔔 Tester la Notification Pushover"):
        envoyer_test_pushover()

# --- 5. TABS ---
t1, t2, t3 = st.tabs(["📊 Portefeuille", "📈 Graphiques", "🌍 Performance"])

with t1:
    for p in positions_calculees:
        a = p['act']
        icone = "⚠️" if p['c_act'] < p['sb'] else ("🟢" if p['pv'] >= 0 else "🔴")
        header = f"{icone} {a['Nom']} | {p['c_act']:.2f}€ | {p['pv']:+.2f}€"
        with st.expander(header):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**PRU:** {p['pru']:.2f}€")
            c2.write(f"**Qté:** {p['qte']}")
            c3.write(f"**Alerte:** {p['sb']:.2f}€")
            if st.button("🗑️", key=f"d_{p['idx']}"):
                st.session_state.mon_portefeuille.pop(p['idx'])
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()
