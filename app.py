import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import base64
import plotly.graph_objects as go
from datetime import date, datetime, timedelta

# --- 1. CONFIGURATION SECRETS ---
try:
    USER_KEY = st.secrets.get("PUSHOVER_USER_KEY")
    API_TOKEN = st.secrets.get("API_TOKEN") or st.secrets.get("PUSHOVER_API_TOKEN")
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
except Exception as e:
    st.error(f"Erreur configuration Secrets : {e}")
    st.stop()

st.set_page_config(page_title="Gestion Portefeuille Pro", layout="wide")

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
def tracer_courbe(df, titre, pru=None, intervalle="1d"):
    if df is None or df.empty:
        st.warning("Pas de données disponibles pour cette période.")
        return

    # --- CORRECTIF POUR L'ERREUR KEYERROR ---
    # Si Yahoo renvoie des colonnes complexes, on ne garde que le premier niveau
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Vérification de la présence de la colonne Close
    if 'Close' not in df.columns:
        st.error(f"Erreur : Colonne 'Close' introuvable dans les données.")
        return

    # Nettoyage
    df = df.dropna(subset=['Close'])
    
    fig = go.Figure()
    
    # Courbe
    fig.add_trace(go.Scatter(
        x=df.index, 
        y=df['Close'].round(2),
        mode='lines',
        line=dict(color='#00FF00', width=1.5),
        name="Prix",
        hovertemplate="<b>Date</b>: %{x|%d/%m/%y}<br><b>Prix</b>: %{y:.2f} €<extra></extra>"
    ))

    # Ligne de PRU
    if pru:
        fig.add_hline(
            y=float(pru), 
            line_dash="dash", 
            line_color="orange", 
            annotation_text=f"PRU: {pru:.2f}€", 
            annotation_position="top left"
        )

    # Configuration des axes (Format jj/mm/yy et 2 décimales)
    fig.update_layout(
        title=dict(text=titre, font=dict(size=18)),
        template="plotly_dark",
        hovermode="x unified",
        xaxis=dict(
            tickformat="%d/%m/%y",
            tickangle=-45,
            showgrid=True,
            gridcolor='rgba(255,255,255,0.1)',
            nticks=20
        ),
        yaxis=dict(
            side="right",
            tickformat=".2f",
            showgrid=True,
            gridcolor='rgba(255,255,255,0.1)',
            ticksuffix=" €"
        ),
        height=500,
        margin=dict(l=20, r=50, t=60, b=80)
    )
    
    st.plotly_chart(fig, use_container_width=True)

# --- 4. CALCULS PORTEFEUILLE ---
tab_p, tab_g, tab_p_hist = st.tabs(["📊 Portefeuille", "📈 Graphiques Actions", "🌍 Historique Portefeuille"])

total_actuel, total_achat, var_jour = 0.0, 0.0, 0.0
donnees_pos = []

if st.session_state.mon_portefeuille:
    for i, act in enumerate(st.session_state.mon_portefeuille):
        try:
            t = yf.Ticker(act['Ticker'])
            h = t.history(period="5d")
            if not h.empty:
                p_act = h['Close'].iloc[-1]
                p_prev = h['Close'].iloc[-2] if len(h) > 1 else p_act
                qte, pru = float(act['Qté']), float(act['PRU'])
                val_l = p_act * qte
                total_actuel += val_l
                total_achat += (pru * qte)
                var_jour += (p_act - p_prev) * qte
                donnees_pos.append({"idx": i, "act": act, "prix": p_act, "val": val_l, "ticker": act['Ticker']})
        except: pass

with tab_p:
    if total_achat > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        pl_g = total_actuel - total_achat
        c2.metric("P/L GLOBAL", f"{pl_g:.2f} €", delta=f"{(pl_g/total_achat*100):+.2f} %")
        c3.metric("VAR. JOUR", f"{var_jour:+.2f} €")
        st.divider()
    for item in donnees_pos:
        a, p = item['act'], item['prix']
        pru, qte = float(a['PRU']), float(a['Qté'])
        pv_l = (p - pru) * qte
        header = f"{'🟢' if pv_l >= 0 else '🔴'} {a['Nom']} | {p:.2f}€ | {pv_l:+.2f}€"
        with st.expander(header):
            col1, col2, col3 = st.columns(3)
            col1.write(f"**Qté :** {qte} | **PRU :** {pru:.2f}€")
            col2.write(f"**Valeur :** {item['val']:.2f}€")
            col3.write(f"**Achat :** {a.get('Date_Achat')}")
            if st.button("Supprimer", key=f"del_{item['idx']}"):
                st.session_state.mon_portefeuille.pop(item['idx'])
                sauvegarder_vers_github(st.session_state.mon_portefeuille); st.rerun()

with tab_g:
    if st.session_state.mon_portefeuille:
        choix = st.selectbox("Action :", [x['Nom'] for x in st.session_state.mon_portefeuille])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        ticker, d_achat, pru_val = info['Ticker'], info['Date_Achat'], float(info['PRU'])
        
        st.subheader(f"Analyses pour {info['Nom']}")
        t_1, t_2, t_3, t_4 = st.tabs(["Depuis l'achat", "Mois", "Semaine", "Journée"])
        
        with t_1:
            df = yf.download(ticker, start=d_achat, progress=False)
            tracer_courbe(df, "Historique depuis l'achat", pru=pru_val)
        with t_2:
            df = yf.download(ticker, start=datetime.now()-timedelta(days=30), progress=False)
            tracer_courbe(df, "Dernier Mois", pru=pru_val)
        with t_3:
            df = yf.download(ticker, start=datetime.now()-timedelta(days=7), progress=False)
            tracer_courbe(df, "Dernière Semaine", pru=pru_val)
        with t_4:
            df = yf.download(ticker, period="1d", interval="5m", progress=False)
            tracer_courbe(df, "Activité du jour (Intraday)", pru=pru_val)

with tab_p_hist:
    st.subheader("Performance du Portefeuille Global")
    # Pour le portefeuille, on agrège les données des tickers présents
    tickers_list = [x['Ticker'] for x in st.session_state.mon_portefeuille]
    if tickers_list:
        p_1, p_2 = st.tabs(["Dernière Semaine", "Journée"])
        with p_1:
            data = yf.download(tickers_list, period="7d", progress=False)['Close']
            # Calcul de la valeur pondérée du portefeuille sur 7j
            hist_port = pd.Series(0, index=data.index)
            for act in st.session_state.mon_portefeuille:
                hist_port += data[act['Ticker']] * float(act['Qté'])
            tracer_courbe(pd.DataFrame({'Close': hist_port}), "Valeur Portefeuille (7 derniers jours)")
        with p_2:
            data = yf.download(tickers_list, period="1d", interval="5m", progress=False)['Close']
            hist_port = pd.Series(0, index=data.index)
            for act in st.session_state.mon_portefeuille:
                hist_port += data[act['Ticker']] * float(act['Qté'])
            tracer_courbe(pd.DataFrame({'Close': hist_port}), "Valeur Portefeuille (Aujourd'hui)")

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("Gestion")
    with st.form("add_form", clear_on_submit=True):
        f_n = st.text_input("Nom")
        f_t = st.text_input("Ticker")
        f_p = st.number_input("PRU", min_value=0.0, format="%.2f")
        f_q = st.number_input("Qté", min_value=0.0, format="%.2f")
        f_d = st.date_input("Date Achat")
        if st.form_submit_button("Ajouter"):
            st.session_state.mon_portefeuille.append({"Nom": f_n, "Ticker": f_t.upper(), "PRU": f_p, "Qté": f_q, "Date_Achat": str(f_d)})
            sauvegarder_vers_github(st.session_state.mon_portefeuille); st.rerun()
    
    up = st.file_uploader("Restaurer CSV", type="csv")
    if up:
        df_up = pd.read_csv(up)
        st.session_state.mon_portefeuille = df_up.to_dict('records')
        sauvegarder_vers_github(st.session_state.mon_portefeuille); st.rerun()


