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
    st.error("Secrets GitHub manquants.")
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
        st.warning("Pas de données.")
        return
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color='#00FF00', width=2), name="Valeur"))
    if pru: fig.add_hline(y=float(pru), line_dash="dash", line_color="orange", annotation_text="PRU")
    if s_h and float(s_h) > 0: fig.add_hline(y=float(s_h), line_color="green", line_width=1.5)
    if s_b and float(s_b) > 0: fig.add_hline(y=float(s_b), line_color="red", line_width=1.5)
    fig.update_layout(template="plotly_dark", hovermode="x unified", height=500, xaxis=dict(tickformat="%d/%m/%y"))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. CALCULS PRÉALABLES (Pour Sidebar & Onglets) ---
positions_calculees = []
total_actuel = 0.0
total_achat = 0.0

for i, act in enumerate(st.session_state.mon_portefeuille):
    try:
        tk = yf.Ticker(act['Ticker'])
        hist = tk.history(period="1d")
        c_act = hist['Close'].iloc[-1] if not hist.empty else 0
        
        pru = float(act['PRU'])
        qte = float(act['Qté'])
        s_b = float(act.get('Seuil_Bas', 0))
        if s_b == 0: s_b = pru * 0.7
        
        val_titre = c_act * qte
        pv_euro = val_titre - (pru * qte)
        pv_perc = (pv_euro / (pru * qte) * 100) if (pru * qte) > 0 else 0
        
        total_actuel += val_titre
        total_achat += (pru * qte)
        
        positions_calculees.append({
            "idx": i, "act": act, "c_act": c_act, "val": val_titre, 
            "pv": pv_euro, "pc": pv_perc, "sb": s_b
        })
    except: continue

# --- 5. BARRE LATÉRALE ---
with st.sidebar:
    st.title("💰 Résumé Global")
    if total_achat > 0:
        diff_global = total_actuel - total_achat
        perc_global = (diff_global / total_achat) * 100
        st.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        st.metric("PLUS-VALUE TOTALE", f"{diff_global:+.2f} €", delta=f"{perc_global:+.2f} %")
    else:
        st.info("Aucune donnée")
    
    st.divider()
    
    with st.form("add_form", clear_on_submit=True):
        st.subheader("➕ Ajouter un titre")
        n, i, t = st.text_input("Nom"), st.text_input("ISIN"), st.text_input("Ticker (ex: MC.PA)")
        p, q = st.number_input("PRU", min_value=0.0), st.number_input("Qté", min_value=0.0)
        d = st.date_input("Achat", value=date.today())
        sh = st.number_input("Seuil Haut", min_value=0.0)
        sb = st.number_input("Seuil Bas (0=Auto)", min_value=0.0)
        if st.form_submit_button("Ajouter"):
            v_sb = sb if sb > 0 else (p * 0.7)
            st.session_state.mon_portefeuille.append({"Nom":n,"ISIN":i,"Ticker":t.upper(),"PRU":p,"Qté":q,"Date_Achat":str(d),"Seuil_Haut":sh,"Seuil_Bas":v_sb})
            sauvegarder_vers_github(st.session_state.mon_portefeuille)
            st.rerun()

# --- 6. ONGLETS ---
tab1, tab2, tab3 = st.tabs(["📊 Portefeuille", "📈 Graphiques Actions", "🌍 Performance Globale"])

with tab1:
    for p in positions_calculees:
        a = p['act']
        # Icône intelligente
        if p['c_act'] > 0 and p['c_act'] < p['sb']:
            icone = "⚠️"
        elif p['pv'] >= 0:
            icone = "🟢"
        else:
            icone = "🔴"

        titre_header = f"{icone} {a['Nom']} | {p['c_act']:.2f}€ | {p['pv']:+.2f}€ ({p['pc']:+.2f}%)"

        with st.expander(titre_header):
            c1, c2, c3, c4 = st.columns([2,2,2,1])
            with c1:
                st.write(f"**ISIN:** {a.get('ISIN')}")
                st.write(f"**PRU:** {float(a['PRU']):.2f}€")
            with c2:
                st.write(f"**Qté:** {a['Qté']}")
                st.write(f"**Valeur Totale:** {p['val']:.2f}€")
            with c3:
                st.write(f"**Seuil Haut:** {a.get('Seuil_Haut', 0):.2f}€")
                st.write(f"**Seuil Bas:** {p['sb']:.2f}€")
            with c4:
                if st.button("✏️", key=f"e_{p['idx']}"): st.session_state[f"m_{p['idx']}"] = True
                if st.button("🗑️", key=f"d_{p['idx']}"):
                    st.session_state.mon_portefeuille.pop(p['idx'])
                    sauvegarder_vers_github(st.session_state.mon_portefeuille)
                    st.rerun()
            
            if st.session_state.get(f"m_{p['idx']}", False):
                with st.form(f"f_{p['idx']}"):
                    n_pru = st.number_input("PRU", value=float(a['PRU']))
                    n_qte = st.number_input("Qté", value=float(a['Qté']))
                    n_sh = st.number_input("Seuil Haut", value=float(a.get('Seuil_Haut', 0)))
                    n_sb = st.number_input("Seuil Bas", value=float(p['sb']))
                    if st.form_submit_button("Enregistrer"):
                        st.session_state.mon_portefeuille[p['idx']].update({"PRU":n_pru,"Qté":n_qte,"Seuil_Haut":n_sh,"Seuil_Bas":n_sb})
                        sauvegarder_vers_github(st
