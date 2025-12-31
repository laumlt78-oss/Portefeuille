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

# --- 2. FONCTIONS TECHNIQUES ---
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
        st.warning("Pas de données disponibles pour tracer le graphique.")
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
    st.session_state.mon_portefeuille = charger_csv_github("portefeuille_data.csv")
if 'ma_watchlist' not in st.session_state:
    st.session_state.ma_watchlist = charger_csv_github("watchlist_data.csv")
if 'mes_dividendes' not in st.session_state:
    st.session_state.mes_dividendes = charger_csv_github("dividendes_data.csv")

# --- 3. RÉCUPÉRATION DES PRIX ---
all_tickers = list(set([x['Ticker'] for x in st.session_state.mon_portefeuille] + [x['Ticker'] for x in st.session_state.ma_watchlist]))
prices = {}

if all_tickers:
    with st.spinner('Actualisation des cours...'):
        for t in all_tickers:
            try:
                tk = yf.Ticker(t)
                # On essaie d'abord la méthode rapide
                price = tk.fast_info.last_price
                if price is None or price == 0:
                    price = tk.history(period="1d")['Close'].iloc[-1]
                prices[t] = float(price)
            except:
                prices[t] = 0.0

# --- 4. CALCULS GLOBAUX ---
total_actuel, total_achat = 0.0, 0.0
positions_calculees = []

for i, act in enumerate(st.session_state.mon_portefeuille):
    try:
        pru = float(act.get('PRU', 0)) if pd.notnull(act.get('PRU')) else 0.0
        qte = float(act.get('Qté', 0)) if pd.notnull(act.get('Qté')) else 0.0
        sh = float(act.get('Seuil_Haut', 0)) if pd.notnull(act.get('Seuil_Haut')) else 0.0
        sb = float(act.get('Seuil_Bas', 0)) if pd.notnull(act.get('Seuil_Bas')) else pru * 0.7
        
        c_act = prices.get(act['Ticker'], 0.0)
        val_titre = c_act * qte
        total_actuel += val_titre
        total_achat += (pru * qte)
        
        positions_calculees.append({
            "idx": i, "act": act, "c_act": c_act, "val": val_titre,
            "pv": val_titre - (pru * qte), "sb": sb, "sh": sh, "pru": pru, "qte": qte
        })
    except: continue

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("💰 Résumé")
    if total_achat > 0:
        st.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        diff = total_actuel - total_achat
        pct = (diff / total_achat * 100)
        st.metric("P/L GLOBAL", f"{diff:+.2f} €", delta=f"{pct:+.2f}%")
    st.divider()
    with st.form("add_form", clear_on_submit=True):
        st.subheader("➕ Ajouter au Portefeuille")
        n, i_code, t = st.text_input("Nom"), st.text_input("ISIN"), st.text_input("Ticker")
        p, q = st.number_input("PRU", min_value=0.0), st.number_input("Qté", min_value=0.0)
        d = st.date_input("Date Achat", value=date.today())
        if st.form_submit_button("Ajouter"):
            if n and t:
                st.session_state.mon_portefeuille.append({"Nom":n, "ISIN":i_code, "Ticker":t.upper(), "PRU":p, "Qté":q, "Date_Achat":str(d), "Seuil_Haut":0, "Seuil_Bas":p*0.7})
                sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                st.rerun()

# --- 6. NAVIGATION ---
t1, t2, t3, t4, t5 = st.tabs(["📊 Portefeuille", "📈 Graphiques", "🌍 Performance", "🔍 Valeurs à surveiller", "💰 Valorisation"])

# --- ONGLET 1 : PORTEFEUILLE ---
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
                st.write(f"**PRU Total:** {(p['pru']*p['qte']):.2f}€")
            with c2:
                st.write(f"**Qté:** {p['qte']}")
                st.write(f"**Valeur Actuelle:** {p['val']:.2f}€")
            with c3:
                st.write(f"**Seuil Haut:** {p['sh']:.2f}€")
                st.write(f"**Seuil Bas:** {p['sb']:.2f}€")
            with c4:
                if st.button("🗑️", key=f"del_{p['idx']}"):
                    st.session_state.mon_portefeuille.pop(p['idx'])
                    sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                    st.rerun()

# --- ONGLET 2 : GRAPHIQUES ---
with t2:
    if st.session_state.mon_portefeuille:
        c_sel, c_per = st.columns([2,1])
        with c_sel: choix = st.selectbox("Choisir une action", [x['Nom'] for x in st.session_state.mon_portefeuille])
        with c_per: periode = st.selectbox("Période", ["Aujourd'hui", "1 mois", "6 mois", "1 an", "Depuis l'achat"])
        
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        
        if periode == "Aujourd'hui":
            df_h = yf.download(info['Ticker'], period="1d", interval="1m", progress=False)
        elif periode == "Depuis l'achat":
            df_h = yf.download(info['Ticker'], start=info.get('Date_Achat', date.today()-timedelta(days=365)), progress=False)
        else:
            mapping = {"1 an":"1y", "6 mois":"6mo", "1 mois":"1mo"}
            df_h = yf.download(info['Ticker'], period=mapping[periode], progress=False)
            
        tracer_courbe(df_h, info['Nom'], pru=info['PRU'], s_h=info.get('Seuil_Haut'), s_b=info.get('Seuil_Bas'))

# --- ONGLET 3 : PERFORMANCE ---
with t3:
    st.subheader("Valeur cumulée du portefeuille (1 mois)")
    tickers = [x['Ticker'] for x in st.session_state.mon_portefeuille]
    if tickers:
        data = yf.download(tickers, period="1mo", progress=False)['Close']
        if not data.empty:
            val_port = pd.Series(0, index=data.index)
            for act in st.session_state.mon_portefeuille:
                t_code = act['Ticker']
                if t_code in data.columns:
                    val_port += data[t_code] * float(act['Qté'])
                elif len(tickers) == 1: # Cas spécial où yfinance renvoie une Serie
                    val_port += data * float(act['Qté'])
            tracer_courbe(pd.DataFrame({'Close': val_port}), "Total Portefeuille")

# --- ONGLET 4 : VALEURS À SURVEILLER ---
with t4:
    st.header("🔍 Valeurs à surveiller")
    if st.button("➕ Nouvelle valeur à surveiller"):
        st.session_state.show_w_form = not st.session_state.get('show_w_form', False)

    if st.session_state.get('show_w_form', False):
        with st.form("watchlist_form"):
            c1, c2, c3 = st.columns(3)
            wn = c1.text_input("Nom de la valeur")
            wi = c2.text_input("Code ISIN")
            wt = c3.text_input("Ticker (Yahoo)")
            ws = st.number_input("Seuil d'alerte (€)", min_value=0.0)
            if st.form_submit_button("Créer la surveillance"):
                if wn and wt:
                    st.session_state.ma_watchlist.append({"Nom": wn, "ISIN": wi, "Ticker": wt.upper(), "Seuil_Alerte": ws})
                    sauvegarder_csv_github(st.session_state.ma_watchlist, "watchlist_data.csv")
                    st.session_state.show_w_form = False
                    st.rerun()

    st.divider()
    for j, w in enumerate(st.session_state.ma_watchlist):
        cur_w = prices.get(w['Ticker'], 0.0)
        col1, col2, col3, col4, col5 = st.columns([2,1,1,1,2])
        col1.write(f"**{w['Nom']}** ({w['ISIN']})")
        col2.write(f"Cours: {cur_w:.2f}€")
        col3.write(f"Seuil: {w.get('Seuil_Alerte', 0):.2f}€")
        
        if col5.button("📥 Acheter / Insérer", key=f"ins_{j}"):
            st.session_state[f"pop_ins_{j}"] = True
            
        if st.session_state.get(f"pop_ins_{j}", False):
            with st.form(f"f_ins_{j}"):
                st.info(f"Ajout de {w['Nom']} au portefeuille")
                fi_q = st.number_input("Nombre d'actions", min_value=1.0)
                fi_p = st.number_input("PRU (€)", value=cur_w)
                fi_sh = st.number_input("Seuil Haut", value=fi_p*1.2)
                fi_sb = st.number_input("Seuil Bas", value=fi_p*0.8)
                if st.form_submit_button("Confirmer l'achat"):
                    st.session_state.mon_portefeuille.append({
                        "Nom": w['Nom'], "ISIN": w['ISIN'], "Ticker": w['Ticker'], 
                        "PRU": fi_p, "Qté": fi_q, "Date_Achat": str(date.today()),
                        "Seuil_Haut": fi_sh, "Seuil_Bas": fi_sb
                    })
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

    if st.session_state.mon_portefeuille:
        df_div = pd.DataFrame(st.session_state.mes_dividendes)
        bilan_data = []
        
        # Initialisation des totaux globaux
        g_investi = 0
        g_actuel = 0
        g_div = 0

        for a in st.session_state.mon_portefeuille:
            p_act = prices.get(a['Ticker'], 0.0)
            qte = float(a.get('Qté', 0))
            total_pru = float(a.get('PRU', 0)) * qte
            val_act = p_act * qte
            sum_div = df_div[df_div['Ticker'] == a['Ticker']]['Montant'].sum() if not df_div.empty else 0.0
            
            # Mise à jour des globaux
            g_investi += total_pru
            g_actuel += val_act
            g_div += sum_div
            
            # Calculs par ligne
            pv_bourse = val_act - total_pru
            perf_bourse = (pv_bourse / total_pru * 100) if total_pru > 0 else 0
            
            pv_reelle = (val_act + sum_div) - total_pru
            perf_reelle = (pv_reelle / total_pru * 100) if total_pru > 0 else 0
            
            bilan_data.append({
                "Action": a['Nom'],
                "Investi": f"{total_pru:.2f}€",
                "+/- Value Bourse": f"{pv_bourse:+.2f}€ ({perf_bourse:+.2f}%)",
                "Dividendes": f"{sum_div:.2f}€",
                "Performance Réelle (+Div)": f"{pv_reelle:+.2f}€ ({perf_reelle:+.2f}%)"
            })
        
        # --- AFFICHAGE DES RÉCAPITULATIFS EN HAUT ---
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Total Investi", f"{g_investi:.2f} €")
        with c2:
            pv_g_bourse = g_actuel - g_investi
            pct_g_bourse = (pv_g_bourse / g_investi * 100) if g_investi > 0 else 0
            st.metric("Bilan Boursier", f"{g_actuel:.2f} €", delta=f"{pv_g_bourse:+.2f}€ ({pct_g_bourse:+.2f}%)")
        with c3:
            richesse_g = g_actuel + g_div
            pv_g_reelle = richesse_g - g_investi
            pct_g_reelle = (pv_g_reelle / g_investi * 100) if g_investi > 0 else 0
            st.metric("Richesse Totale", f"{richesse_g:.2f} €", delta=f"{pv_g_reelle:+.2f}€ ({pct_g_reelle:+.2f}%)", delta_color="normal")

        st.divider()
        st.subheader("Détail par valeur")
        st.table(pd.DataFrame(bilan_data))
    else:
        st.info("Le portefeuille est vide.")
