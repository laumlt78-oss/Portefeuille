import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import base64
import plotly.graph_objects as go
from datetime import date, datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Portefeuille Expert", layout="wide", initial_sidebar_state="expanded")

# CSS pour améliorer la lisibilité des alertes
st.markdown("""
    <style>
    .stMetric { background-color: rgba(255, 255, 255, 0.05); padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

try:
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
except:
    st.error("Secrets GitHub manquants ou mal configurés.")
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
        st.warning("Pas de données disponibles.")
        return
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color='#00FF00', width=2), name="Prix"))
    
    if pru: fig.add_hline(y=float(pru), line_dash="dash", line_color="orange", annotation_text="PRU")
    if s_h and float(s_h) > 0: fig.add_hline(y=float(s_h), line_color="#00FF00", line_width=1.5, annotation_text="Haut")
    if s_b and float(s_b) > 0: fig.add_hline(y=float(s_b), line_color="#FF0000", line_width=1.5, annotation_text="Bas")

    fig.update_layout(template="plotly_dark", hovermode="x unified", height=500,
                      xaxis=dict(tickformat="%d/%m/%y", tickangle=-45, nticks=20),
                      yaxis=dict(side="right", ticksuffix=" €"))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. BARRE LATÉRALE (AJOUT) ---
with st.sidebar:
    st.header("⚙️ Gestion")
    with st.form("add_form", clear_on_submit=True):
        st.subheader("➕ Ajouter un Titre")
        n, i, t = st.text_input("Nom"), st.text_input("ISIN"), st.text_input("Ticker (ex: MC.PA)")
        p, q = st.number_input("PRU", min_value=0.0), st.number_input("Qté", min_value=0.0)
        d = st.date_input("Date d'achat", value=date.today())
        st.write("---")
        sh = st.number_input("Seuil Haut (Vente)", min_value=0.0)
        sb = st.number_input("Seuil Bas (Laissez 0 pour PRU -30%)", min_value=0.0)
        if st.form_submit_button("Ajouter au Portefeuille"):
            if n and t:
                val_sb = sb if sb > 0 else (p * 0.7)
                st.session_state.mon_portefeuille.append({
                    "Nom": n, "ISIN": i, "Ticker": t.upper(), "PRU": p, "Qté": q, 
                    "Date_Achat": str(d), "Seuil_Haut": sh, "Seuil_Bas": val_sb
                })
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()

# --- 5. ONGLETS PRINCIPAUX ---
tab1, tab2, tab3 = st.tabs(["📊 Portefeuille", "📈 Graphiques Actions", "🌍 Performance Globale"])

# Pré-chargement des prix pour les alertes
donnees_pos = []
total_actuel = 0.0
total_achat = 0.0

if st.session_state.mon_portefeuille:
    for i, act in enumerate(st.session_state.mon_portefeuille):
        try:
            # Calcul auto du seuil bas si absent ou 0 (rétro-compatibilité)
            if float(act.get('Seuil_Bas', 0)) == 0:
                act['Seuil_Bas'] = float(act['PRU']) * 0.7
            
            ticker = yf.Ticker(act['Ticker'])
            p_act = ticker.history(period="1d")['Close'].iloc[-1]
            val_titre = p_act * float(act['Qté'])
            total_actuel += val_titre
            total_achat += (float(act['PRU']) * float(act['Qté']))
            donnees_pos.append({"idx": i, "act": act, "prix": p_act, "val": val_titre})
        except: continue

with tab1:
    if total_achat > 0:
        col_m1, col_m2 = st.columns(2)
        col_m1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        pl_global = total_actuel - total_achat
        col_m2.metric("PLUS-VALUE GLOBALE", f"{pl_global:.2f} €", delta=f"{(pl_global/total_achat*100):+.2f}%")
        st.write("---")

    for item in donnees_pos:
        a, idx, p_act = item['act'], item['idx'], item['prix']
        s_bas = float(a['Seuil_Bas'])
        s_haut = float(a.get('Seuil_Haut', 0))
        
        # ALERTE VISUELLE : Si prix < seuil bas -> Rouge + Emoji
        if p_act < s_bas:
            label = f"⚠️ ALERTE : {a['Nom']} ({a['Ticker']}) - COURS SOUS LE SEUIL !"
            color = "red"
        elif s_haut > 0 and p_act > s_haut:
            label = f"🚀 OBJECTIF ATTEINT : {a['Nom']} ({a['Ticker']})"
            color = "green"
        else:
            label = f"📌 {a['Nom']} ({a['Ticker']})"
            color = "white"

        with st.expander(label):
            st.markdown(f"### <span style='color:{color}'>{label}</span>", unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns([2,2,2,1])
            with c1:
                st.write(f"**ISIN:** {a.get('ISIN')}")
                st.write(f"**Cours Actuel:** {p_act:.2f} €")
                st.write(f"**PRU:** {float(a['PRU']):.2f} €")
            with c2:
                st.write(f"**Quantité:** {a['Qté']}")
                st.write(f"**Valeur Totale:** {item['val']:.2f} €")
            with c3:
                st.write(f"**Seuil Haut:** {s_haut:.2f} €")
                st.write(f"**Seuil Bas:** {s_bas:.2f} €")
            
            with c4:
                if st.button("✏️ Modifier", key=f"edit_btn_{idx}"):
                    st.session_state[f"edit_mode_{idx}"] = True
                if st.button("🗑️ Supprimer", key=f"del_btn_{idx}"):
                    st.session_state.mon_portefeuille.pop(idx)
                    sauvegarder_vers_github(st.session_state.mon_portefeuille)
                    st.rerun()

            # Formulaire de modification
            if st.session_state.get(f"edit_mode_{idx}", False):
                with st.form(f"form_edit_{idx}"):
                    n_pru = st.number_input("PRU", value=float(a['PRU']))
                    n_qte = st.number_input("Quantité", value=float(a['Qté']))
                    n_sh = st.number_input("Seuil Haut", value=float(s_haut))
                    n_sb = st.number_input("Seuil Bas", value=float(s_bas))
                    if st.form_submit_button("Sauvegarder les modifications"):
                        st.session_state.mon_portefeuille[idx].update({
                            "PRU": n_pru, "Qté": n_qte, "Seuil_Haut": n_sh, "Seuil_Bas": n_sb
                        })
                        sauvegarder_vers_github(st.session_state.mon_portefeuille)
                        del st.session_state[f"edit_mode_{idx}"]
                        st.rerun()

with tab2:
    if st.session_state.mon_portefeuille:
        choix = st.selectbox("Choisir une action à analyser", [x['Nom'] for x in st.session_state.mon_portefeuille])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        
        sub_t1, sub_t2 = st.tabs(["Historique Complet", "Séance du jour"])
        with sub_t1:
            df = yf.download(info['Ticker'], start=info['Date_Achat'], progress=False)
            tracer_courbe(df, f"Analyse {info['Nom']}", pru=info['PRU'], s_h=info.get('Seuil_Haut'), s_b=info.get('Seuil_Bas'))
        with sub_t2:
            df = yf.download(info['Ticker'], period="1d", interval="5m", progress=False)
            tracer_courbe(df, "Intraday (5 min)", pru=info['PRU'], s_h=info.get('Seuil_Haut'), s_b=info.get('Seuil_Bas'))

with tab3:
    tickers = [x['Ticker'] for x in st.session_state.mon_portefeuille]
    if tickers:
        st.subheader("Évolution de la valeur totale (7 derniers jours)")
        data = yf.download(tickers, period="7d", progress=False)['Close']
        if not data.empty:
            if isinstance(data, pd.Series): data = data.to_frame()
            val_port = pd.Series(0, index=data.index)
            for act in st.session_state.mon_portefeuille:
                if act['Ticker'] in data.columns:
                    val_port += data[act['Ticker']] * float(act['Qté'])
            tracer_courbe(pd.DataFrame({'Close': val_port}), "Performance Portefeuille")
