import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import base64
import plotly.graph_objects as go
from datetime import date, datetime, timedelta

# --- 1. CONFIGURATION ---
try:
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
except Exception as e:
    st.error("Secrets GitHub manquants.")
    st.stop()

st.set_page_config(page_title="Mon Portefeuille Pro", layout="wide")

# --- 2. FONCTIONS GITHUB ---
FICHIER_DATA = "portefeuille_data.csv"
HEADERS_GH = {"Authorization": f"token {GH_TOKEN}"}

def charger_depuis_github():
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{FICHIER_DATA}"
    try:
        r = requests.get(url, headers=HEADERS_GH, timeout=5)
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
    r_get = requests.get(url, headers=HEADERS_GH, timeout=5)
    sha = r_get.json().get('sha') if r_get.status_code == 200 else None
    payload = {"message": "Update", "content": base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')}
    if sha: payload["sha"] = sha
    requests.put(url, headers=HEADERS_GH, json=payload, timeout=5)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_depuis_github()

# --- 3. FONCTION GRAPHIQUE (VOTRE FORMAT) ---
def tracer_courbe(df, titre, pru=None):
    if df is None or df.empty:
        st.warning("Pas de données.")
        return
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df.index, y=df['Close'].round(2),
        mode='lines', line=dict(color='#00FF00', width=1.5),
        hovertemplate="<b>Date</b>: %{x|%d/%m/%y}<br><b>Prix</b>: %{y:.2f} €<extra></extra>"
    ))
    if pru:
        fig.add_hline(y=float(pru), line_dash="dash", line_color="orange", annotation_text=f"PRU: {pru:.2f}€")

    fig.update_layout(
        title=titre, template="plotly_dark", hovermode="x unified",
        xaxis=dict(tickformat="%d/%m/%y", tickangle=-45, nticks=20, showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(side="right", tickformat=".2f", ticksuffix=" €", showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        height=450, margin=dict(l=20, r=50, t=50, b=80)
    )
    st.plotly_chart(fig, use_container_width=True)

# --- 4. AFFICHAGE PRINCIPAL ---
tab_p, tab_g = st.tabs(["📊 Portefeuille", "📈 Graphiques"])

with tab_p:
    total_actuel, total_achat = 0.0, 0.0
    
    if not st.session_state.mon_portefeuille:
        st.info("Votre portefeuille est vide. Utilisez la barre latérale pour ajouter des actions.")
    else:
        # On affiche d'abord les métriques globales
        for act in st.session_state.mon_portefeuille:
            try:
                # On récupère le prix actuel rapidement
                d = yf.download(act['Ticker'], period="1d", progress=False)
                if isinstance(d.columns, pd.MultiIndex): d.columns = d.columns.get_level_values(0)
                prix_c = d['Close'].iloc[-1]
                total_actuel += prix_c * float(act['Qté'])
                total_achat += float(act['PRU']) * float(act['Qté'])
            except: pass

        if total_achat > 0:
            c1, c2 = st.columns(2)
            c1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
            diff = total_actuel - total_achat
            c2.metric("P/L GLOBAL", f"{diff:.2f} €", delta=f"{(diff/total_achat*100):+.2f} %")
            st.divider()

        # Liste des actions avec possibilité de suppression/modification
        for i, act in enumerate(st.session_state.mon_portefeuille):
            with st.expander(f"⚙️ {act['Nom']} ({act['Ticker']})"):
                col1, col2, col3 = st.columns([2, 2, 1])
                # Affichage des infos
                col1.write(f"**Quantité :** {act['Qté']}")
                col1.write(f"**PRU :** {act['PRU']} €")
                col2.write(f"**Date Achat :** {act.get('Date_Achat', 'N/A')}")
                
                # Bouton de suppression
                if col3.button("🗑️ Supprimer", key=f"del_{i}"):
                    st.session_state.mon_portefeuille.pop(i)
                    sauvegarder_vers_github(st.session_state.mon_portefeuille)
                    st.rerun()

with tab_g:
    if st.session_state.mon_portefeuille:
        choix = st.selectbox("Action à analyser :", [x['Nom'] for x in st.session_state.mon_portefeuille])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        
        sub1, sub2, sub3 = st.tabs(["Depuis l'achat", "Mois", "Journée"])
        with sub1:
            df = yf.download(info['Ticker'], start=info['Date_Achat'], progress=False)
            tracer_courbe(df, f"Historique {info['Nom']}", pru=info['PRU'])
        with sub2:
            df = yf.download(info['Ticker'], start=datetime.now()-timedelta(days=30), progress=False)
            tracer_courbe(df, "Derniers 30 jours", pru=info['PRU'])
        with sub3:
            df = yf.download(info['Ticker'], period="1d", interval="5m", progress=False)
            tracer_courbe(df, "Aujourd'hui", pru=info['PRU'])

# --- 5. BARRE LATÉRALE (SIDEBAR) ---
with st.sidebar:
    st.header("➕ Ajouter une Action")
    with st.form("form_ajout", clear_on_submit=True):
        n = st.text_input("Nom de l'entreprise")
        t = st.text_input("Ticker (ex: OR.PA)")
        p = st.number_input("PRU (€)", min_value=0.0, format="%.2f")
        q = st.number_input("Quantité", min_value=0.0, format="%.2f")
        d = st.date_input("Date d'achat")
        if st.form_submit_button("Ajouter"):
            if n and t:
                nouvelle = {"Nom": n, "Ticker": t.upper(), "PRU": p, "Qté": q, "Date_Achat": str(d)}
                st.session_state.mon_portefeuille.append(nouvelle)
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()
    
    st.divider()
    st.header("💾 Sauvegarde")
    up = st.file_uploader("Importer un CSV", type="csv")
    if up:
        df_up = pd.read_csv(up)
        st.session_state.mon_portefeuille = df_up.to_dict('records')
        sauvegarder_vers_github(st.session_state.mon_portefeuille)
        st.success("Import réussi !")
        st.rerun()
    
    # Export
    if st.session_state.mon_portefeuille:
        csv = pd.DataFrame(st.session_state.mon_portefeuille).to_csv(index=False)
        st.download_button("📥 Télécharger Backup CSV", csv, "mon_portefeuille.csv", "text/csv")
