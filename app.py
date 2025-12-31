import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import base64
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from io import StringIO

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Portefeuille Expert", layout="wide", initial_sidebar_state="expanded")

try:
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
except:
    st.error("Secrets manquants dans Streamlit Cloud.")
    st.stop()

# --- 2. FONCTIONS TECHNIQUES (GÉNÉRIQUES) ---
def charger_csv_github(nom_fichier):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{nom_fichier}"
    try:
        r = requests.get(url, headers={"Authorization": f"token {GH_TOKEN}"}, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            return pd.read_csv(StringIO(content)).to_dict('records')
    except: pass
    return []

def sauvegarder_csv_github(liste, nom_fichier):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{nom_fichier}"
    df = pd.DataFrame(liste)
    csv_content = df.to_csv(index=False)
    r_get = requests.get(url, headers={"Authorization": f"token {GH_TOKEN}"}, timeout=10)
    sha = r_get.json().get('sha') if r_get.status_code == 200 else None
    payload = {"message": f"Sync {nom_fichier}", "content": base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')}
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

# Initialisation des sessions d'état
if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_csv_github("portefeuille_data.csv")
if 'ma_watchlist' not in st.session_state:
    st.session_state.ma_watchlist = charger_csv_github("watchlist_data.csv")
if 'mes_dividendes' not in st.session_state:
    st.session_state.mes_dividendes = charger_csv_github("dividendes_data.csv")

# --- 3. CALCULS TEMPS RÉEL ---
all_tickers = list(set([x['Ticker'] for x in st.session_state.mon_portefeuille] + [x['Ticker'] for x in st.session_state.ma_watchlist]))
prices = {}
if all_tickers:
    try:
        # Récupération groupée pour plus de rapidité
        data_prices = yf.download(all_tickers, period="1d", progress=False)['Close']
        for t in all_tickers:
            if isinstance(data_prices, pd.DataFrame):
                prices[t] = data_prices[t].iloc[-1] if t in data_prices.columns else 0
            else: # Si un seul ticker, download renvoie une Series
                prices[t] = data_prices.iloc[-1]
    except: pass

# --- 4. SIDEBAR ---
total_actuel, total_achat = 0.0, 0.0
for act in st.session_state.mon_portefeuille:
    total_actuel += prices.get(act['Ticker'], 0) * float(act.get('Qté', 0))
    total_achat += float(act.get('PRU', 0)) * float(act.get('Qté', 0))

with st.sidebar:
    st.title("💰 Résumé")
    if total_achat > 0:
        st.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        st.metric("P/L GLOBAL", f"{(total_actuel-total_achat):+.2f} €", delta=f"{((total_actuel-total_achat)/total_achat*100):+.2f}%")
    st.divider()
    with st.form("add_form", clear_on_submit=True):
        st.subheader("➕ Ajouter au Portefeuille")
        n, i, t = st.text_input("Nom"), st.text_input("ISIN"), st.text_input("Ticker")
        p, q = st.number_input("PRU", min_value=0.0), st.number_input("Qté", min_value=0.0)
        d = st.date_input("Date Achat", value=date.today())
        if st.form_submit_button("Ajouter"):
            if n and t:
                st.session_state.mon_portefeuille.append({"Nom":n, "ISIN":i, "Ticker":t.upper(), "PRU":p, "Qté":q, "Date_Achat":str(d), "Seuil_Haut":0, "Seuil_Bas":p*0.7})
                sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                st.rerun()

# --- 5. NAVIGATION ---
t1, t2, t3, t4, t5 = st.tabs(["📊 Portefeuille", "📈 Graphiques", "🌍 Performance", "🔍 Valeurs à surveiller", "💰 Valorisation"])

# --- ONGLET 1 : PORTEFEUILLE ---
with t1:
    for i, a in enumerate(st.session_state.mon_portefeuille):
        c_act = prices.get(a['Ticker'], 0)
        pv = (c_act - float(a['PRU'])) * float(a['Qté'])
        icone = "🟢" if pv >= 0 else "🔴"
        header = f"{icone} {a['Nom']} | {c_act:.2f}€ | {pv:+.2f}€"
        with st.expander(header):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            with c1:
                st.write(f"**ISIN:** {a.get('ISIN')}")
                st.write(f"**PRU Unitaire:** {float(a['PRU']):.2f}€")
            with c2:
                st.write(f"**Qté:** {a['Qté']}")
                st.write(f"**Valeur Actuelle:** {(c_act * float(a['Qté'])):.2f}€")
            with c3:
                st.write(f"**Seuil Haut:** {a.get('Seuil_Haut')}€")
                st.write(f"**Seuil Bas:** {a.get('Seuil_Bas')}€")
            with c4:
                if st.button("🗑️", key=f"del_{i}"):
                    st.session_state.mon_portefeuille.pop(i)
                    sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                    st.rerun()

# --- ONGLET 2 & 3 (VOS GRAPHES) ---
with t2:
    if st.session_state.mon_portefeuille:
        choix = st.selectbox("Action", [x['Nom'] for x in st.session_state.mon_portefeuille])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        df_h = yf.download(info['Ticker'], period="1y", progress=False)
        tracer_courbe(df_h, info['Nom'], pru=info['PRU'], s_h=info.get('Seuil_Haut'), s_b=info.get('Seuil_Bas'))

with t3:
    st.info("Performance historique du portefeuille consolidé (1 mois)")
    # Votre code de courbe cumulée ici...

# --- ONGLET 4 : VALEURS À SURVEILLER ---
with t4:
    st.header("🔍 Valeurs à surveiller")
    
    if st.button("➕ Nouvelle valeur à surveiller"):
        st.session_state.show_w_form = True

    if st.session_state.get('show_w_form', False):
        with st.form("watchlist_form"):
            c1, c2, c3 = st.columns(3)
            wn = c1.text_input("Nom de la valeur")
            wi = c2.text_input("Code ISIN")
            wt = c3.text_input("Ticker (Yahoo)")
            ws = st.number_input("Seuil d'alerte (€)", min_value=0.0)
            if st.form_submit_button("Créer la surveillance"):
                st.session_state.ma_watchlist.append({"Nom": wn, "ISIN": wi, "Ticker": wt.upper(), "Seuil_Alerte": ws})
                sauvegarder_csv_github(st.session_state.ma_watchlist, "watchlist_data.csv")
                st.session_state.show_w_form = False
                st.rerun()

    st.divider()
    for j, w in enumerate(st.session_state.ma_watchlist):
        cur_w = prices.get(w['Ticker'], 0)
        col1, col2, col3, col4, col5 = st.columns([2,1,1,1,2])
        col1.write(f"**{w['Nom']}** ({w['ISIN']})")
        col2.write(f"Cours: {cur_w:.2f}€")
        col3.write(f"Seuil: {w['Seuil_Alerte']:.2f}€")
        
        if col5.button("📥 Acheter / Insérer", key=f"ins_{j}"):
            st.session_state[f"pop_ins_{j}"] = True
            
        if st.session_state.get(f"pop_ins_{j}", False):
            with st.form(f"f_ins_{j}"):
                st.info(f"Ajout de {w['Nom']} au portefeuille")
                fi_q = st.number_input("Nombre d'actions", min_value=1.0)
                fi_p = st.number_input("PRU (€)", value=cur_w)
                fi_sh = st.number_input("Seuil Haut", value=fi_p*1.2)
                fi_sb = st.number_input("Seuil Bas", value=fi_p*0.8)
                if st.form_submit_button("Confirmer l'insertion"):
                    # Ajouter au portefeuille
                    st.session_state.mon_portefeuille.append({
                        "Nom": w['Nom'], "ISIN": w['ISIN'], "Ticker": w['Ticker'], 
                        "PRU": fi_p, "Qté": fi_q, "Date_Achat": str(date.today()),
                        "Seuil_Haut": fi_sh, "Seuil_Bas": fi_sb
                    })
                    # Supprimer de la watchlist
                    st.session_state.ma_watchlist.pop(j)
                    sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                    sauvegarder_csv_github(st.session_state.ma_watchlist, "watchlist_data.csv")
                    st.session_state[f"pop_ins_{j}"] = False
                    st.rerun()

# --- ONGLET 5 : VALORISATION ---
with t5:
    st.header("💰 Valorisation & Dividendes")
    
    with st.expander("➕ Déclarer un dividende"):
        with st.form("div_form"):
            dt = st.selectbox("Action concernée", [x['Ticker'] for x in st.session_state.mon_portefeuille])
            dd = st.date_input("Date du versement")
            dm = st.number_input("Montant net reçu (€)", min_value=0.01)
            if st.form_submit_button("Enregistrer"):
                st.session_state.mes_dividendes.append({"Ticker": dt, "Date": str(dd), "Montant": dm})
                sauvegarder_csv_github(st.session_state.mes_dividendes, "dividendes_data.csv")
                st.success("Dividende ajouté !")
                st.rerun()

    # Bilan de valorisation
    df_div = pd.DataFrame(st.session_state.mes_dividendes)
    bilan_data = []
    for a in st.session_state.mon_portefeuille:
        p_act = prices.get(a['Ticker'], 0)
        qte = float(a['Qté'])
        total_pru = float(a['PRU']) * qte
        val_act = p_act * qte
        
        # Somme des dividendes pour ce ticker
        sum_div = 0
        if not df_div.empty:
            sum_div = df_div[df_div['Ticker'] == a['Ticker']]['Montant'].sum()
        
        perf_div = ((val_act + sum_div - total_pru) / total_pru * 100) if total_pru > 0 else 0
        
        bilan_data.append({
            "Action": a['Nom'],
            "Plus-value latente": f"{(val_act - total_pru):.2f}€",
            "Dividendes": f"{sum_div:.2f}€",
            "Rendement Réel (%)": f"{perf_div:+.2f}%"
        })
    
    st.table(pd.DataFrame(bilan_data))
