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
    st.error("Secrets manquants dans Streamlit Cloud.")
    st.stop()

# --- 2. FONCTIONS TECHNIQUES ---
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

def tracer_courbe(df, titre, pru=None, s_h=None, s_b=None):
    if df is None or df.empty:
        st.warning("Pas de données disponibles.")
        return
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color='#00FF00', width=2), name="Prix"))
    if pru: fig.add_hline(y=float(pru), line_dash="dash", line_color="orange", annotation_text="PRU")
    if s_h and float(s_h) > 0: fig.add_hline(y=float(s_h), line_color="cyan", line_width=1, annotation_text="Objectif")
    if s_b and float(s_b) > 0: fig.add_hline(y=float(s_b), line_color="red", line_width=1, annotation_text="Alerte")
    fig.update_layout(template="plotly_dark", hovermode="x unified", height=500, margin=dict(l=10, r=10, t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

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
        s_haut = float(act.get('Seuil_Haut', 0)) if pd.notnull(act.get('Seuil_Haut')) else 0.0
        sb_val = act.get('Seuil_Bas')
        s_bas = float(sb_val) if pd.notnull(sb_val) and float(sb_val) > 0 else pru * 0.7
        
        tk = yf.Ticker(act['Ticker'])
        c_act = tk.fast_info.last_price
        if c_act is None or c_act == 0:
            hist = tk.history(period="1d")
            c_act = hist['Close'].iloc[-1] if not hist.empty else 0
            
        val_titre = c_act * qte
        total_actuel += val_titre
        total_achat += (pru * qte)
        
        positions_calculees.append({
            "idx": i, "act": act, "c_act": c_act, "val": val_titre, 
            "pv": val_titre - (pru * qte), "sb": s_bas, "sh": s_haut, "pru": pru, "qte": qte
        })
    except: continue

# --- 4. SIDEBAR ---
with st.sidebar:
    st.title("💰 Résumé")
    if total_achat > 0:
        st.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        st.metric("P/L GLOBAL", f"{(total_actuel-total_achat):+.2f} €", delta=f"{((total_actuel-total_achat)/total_achat*100):+.2f}%")
    st.divider()
    with st.form("add_form", clear_on_submit=True):
        st.subheader("➕ Ajouter")
        n, i, t = st.text_input("Nom"), st.text_input("ISIN"), st.text_input("Ticker")
        p, q = st.number_input("PRU", min_value=0.0), st.number_input("Qté", min_value=0.0)
        d = st.date_input("Date Achat", value=date.today())
        if st.form_submit_button("Ajouter"):
            if n and t:
                st.session_state.mon_portefeuille.append({"Nom":n, "ISIN":i, "Ticker":t.upper(), "PRU":p, "Qté":q, "Date_Achat":str(d), "Seuil_Haut":0, "Seuil_Bas":p*0.7})
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()

# --- 5. ONGLETS ---
t1, t2, t3 = st.tabs(["📊 Portefeuille", "📈 Graphiques", "🌍 Performance"])

with t1:
    for p in positions_calculees:
        a = p['act']
        icone = "⚠️" if p['c_act'] < p['sb'] else ("🟢" if p['pv'] >= 0 else "🔴")
        header = f"{icone} {a['Nom']} | {p['c_act']:.2f}€ | {p['pv']:+.2f}€"
        with st.expander(header):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            with c1:
                st.write(f"**ISIN:** {a.get('ISIN', 'N/A')}")
                st.write(f"**PRU Unitaire:** {p['pru']:.2f}€")
                st.write(f"**PRU Total:** {p['pru']*p['qte']:.2f}€") # Ajout PRU Total
            with c2:
                st.write(f"**Qté:** {p['qte']}")
                st.write(f"**Valeur Actuelle:** {p['val']:.2f}€")
            with c3:
                st.write(f"**Seuil Haut:** {p['sh']:.2f}€")
                st.write(f"**Seuil Bas:** {p['sb']:.2f}€")
                st.write(f"**Achat:** {a.get('Date_Achat')}")
            with c4:
                # Bouton Éditer
                if st.button("✏️", key=f"edit_btn_{p['idx']}"):
                    st.session_state[f"editing_{p['idx']}"] = True
                # Bouton Supprimer
                if st.button("🗑️", key=f"del_{p['idx']}"):
                    st.session_state.mon_portefeuille.pop(p['idx'])
                    sauvegarder_vers_github(st.session_state.mon_portefeuille)
                    st.rerun()
            
            # Formulaire d'édition (s'affiche si on clique sur le crayon)
            if st.session_state.get(f"editing_{p['idx']}", False):
                with st.form(f"edit_form_{p['idx']}"):
                    new_pru = st.number_input("Nouveau PRU", value=p['pru'])
                    new_qte = st.number_input("Nouvelle Quantité", value=p['qte'])
                    new_sh = st.number_input("Nouveau Seuil Haut", value=p['sh'])
                    new_sb = st.number_input("Nouveau Seuil Bas", value=p['sb'])
                    if st.form_submit_button("Valider"):
                        st.session_state.mon_portefeuille[p['idx']].update({
                            "PRU": new_pru, "Qté": new_qte, "Seuil_Haut": new_sh, "Seuil_Bas": new_sb
                        })
                        sauvegarder_vers_github(st.session_state.mon_portefeuille)
                        st.session_state[f"editing_{p['idx']}"] = False
                        st.rerun()

with t2:
    if st.session_state.mon_portefeuille:
        c_sel, c_per = st.columns([2,1])
        with c_sel: choix = st.selectbox("Action", [x['Nom'] for x in st.session_state.mon_portefeuille])
        with c_per: periode = st.selectbox("Période", ["Aujourd'hui", "Depuis l'achat", "1 an", "6 mois", "1 mois"])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        if periode == "Aujourd'hui":
            df_h = yf.download(info['Ticker'], period="1d", interval="1m", progress=False)
        elif periode == "Depuis l'achat":
            df_h = yf.download(info['Ticker'], start=info.get('Date_Achat', date.today()-timedelta(days=365)), progress=False)
        else:
            mapping = {"1 an":"1y", "6 mois":"6mo", "1 mois":"1mo"}
            df_h = yf.download(info['Ticker'], period=mapping[periode], progress=False)
        tracer_courbe(df_h, info['Nom'], pru=info['PRU'], s_h=info.get('Seuil_Haut'), s_b=info.get('Seuil_Bas'))

with t3:
    st.subheader("Valeur cumulée du portefeuille (1 mois)")
    tickers = [x['Ticker'] for x in st.session_state.mon_portefeuille]
    if tickers:
        data = yf.download(tickers, period="1mo", progress=False)['Close']
        if not data.empty:
            if isinstance(data, pd.Series): data = data.to_frame()
            val_port = pd.Series(0, index=data.index)
            for act in st.session_state.mon_portefeuille:
                if act['Ticker'] in data.columns:
                    val_port += data[act['Ticker']] * float(act['Qté'])
            tracer_courbe(pd.DataFrame({'Close': val_port}), "Total Portefeuille")
