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
        st.warning(f"Pas de données pour {titre}")
        return
    # Nettoyage MultiIndex yfinance
    if isinstance(df.columns, pd.MultiIndex): 
        df.columns = df.columns.get_level_values(0)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color='#00FF00', width=2), name="Prix"))
    if pru: fig.add_hline(y=float(pru), line_dash="dash", line_color="orange", annotation_text="PRU")
    if s_h and float(s_h) > 0: fig.add_hline(y=float(s_h), line_color="cyan", line_width=1, annotation_text="Objectif")
    if s_b and float(s_b) > 0: fig.add_hline(y=float(s_b), line_color="red", line_width=1, annotation_text="Alerte")
    fig.update_layout(template="plotly_dark", title=titre, hovermode="x unified", height=500, margin=dict(l=10, r=10, t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

# Initialisation
for key in ['mon_portefeuille', 'ma_watchlist', 'mes_dividendes']:
    if key not in st.session_state:
        st.session_state[key] = charger_csv_github(f"{key.replace('mon_','').replace('ma_','').replace('mes_','')}_data.csv")

# --- 3. RÉCUPÉRATION DES PRIX ---
all_tickers = list(set([x['Ticker'] for x in st.session_state.mon_portefeuille] + [x['Ticker'] for x in st.session_state.ma_watchlist]))
prices = {}
if all_tickers:
    for t in all_tickers:
        try:
            tk = yf.Ticker(t)
            p = tk.fast_info.last_price
            if p is None or p == 0: p = tk.history(period="1d")['Close'].iloc[-1]
            prices[t] = float(p)
        except: prices[t] = 0.0

# --- 4. CALCULS GLOBAUX ---
total_actuel, total_achat = 0.0, 0.0
positions_calculees = []
for i, act in enumerate(st.session_state.mon_portefeuille):
    try:
        pru = float(act.get('PRU', 0))
        qte = float(act.get('Qté', 0))
        c_act = prices.get(act['Ticker'], 0.0)
        val_titre = c_act * qte
        total_actuel += val_titre
        total_achat += (pru * qte)
        positions_calculees.append({
            "idx": i, "act": act, "c_act": c_act, "val": val_titre,
            "pv": val_titre - (pru * qte), "pru": pru, "qte": qte,
            "sh": float(act.get('Seuil_Haut', 0)), "sb": float(act.get('Seuil_Bas', 0))
        })
    except: continue

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("💰 Mon Portefeuille")
    if total_achat > 0:
        st.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        diff = total_actuel - total_achat
        pct = (diff / total_achat * 100)
        st.metric("P/L GLOBAL", f"{diff:+.2f} €", delta=f"{pct:+.2f}%")

# --- 6. ONGLETS ---
t1, t2, t3, t4, t5 = st.tabs(["📊 Portefeuille", "📈 Graphiques", "🌍 Performance", "🔍 Watchlist", "💰 Valorisation"])

with t1:
    for p in positions_calculees:
        a = p['act']
        icone = "🟢" if p['pv'] >= 0 else "🔴"
        with st.expander(f"{icone} {a['Nom']} | {p['c_act']:.2f}€ | {p['pv']:+.2f}€"):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            with c1:
                st.write(f"**ISIN:** {a.get('ISIN')}")
                st.write(f"**Ticker:** {a.get('Ticker')}")
                st.write(f"**PRU Unitaire:** {p['pru']:.2f}€")
            with c2:
                st.write(f"**Qté:** {p['qte']}")
                st.write(f"**PRU Total:** {(p['pru']*p['qte']):.2f}€")
                st.write(f"**Valeur Actuelle:** {p['val']:.2f}€")
            with c3:
                st.write(f"**Seuil Haut:** {p['sh']:.2f}€")
                st.write(f"**Seuil Bas:** {p['sb']:.2f}€")
                st.write(f"**Date Achat:** {a.get('Date_Achat')}")
            with c4:
                if st.button("✏️", key=f"ed_{p['idx']}"): st.session_state[f"edit_{p['idx']}"] = True
                if st.button("🗑️", key=f"del_{p['idx']}"):
                    st.session_state.mon_portefeuille.pop(p['idx'])
                    sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                    st.rerun()
            if st.session_state.get(f"edit_{p['idx']}", False):
                with st.form(f"form_ed_{p['idx']}"):
                    n_pru = st.number_input("Nouveau PRU", value=p['pru'])
                    n_qte = st.number_input("Nouvelle Qté", value=p['qte'])
                    n_sh = st.number_input("Seuil Haut", value=p['sh'])
                    n_sb = st.number_input("Seuil Bas", value=p['sb'])
                    if st.form_submit_button("Sauvegarder"):
                        st.session_state.mon_portefeuille[p['idx']].update({"PRU":n_pru, "Qté":n_qte, "Seuil_Haut":n_sh, "Seuil_Bas":n_sb})
                        sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                        st.session_state[f"edit_{p['idx']}"] = False
                        st.rerun()

with t2:
    if st.session_state.mon_portefeuille:
        c_a, c_p = st.columns([2,1])
        choix = c_a.selectbox("Action", [x['Nom'] for x in st.session_state.mon_portefeuille])
        per = c_p.selectbox("Période", ["Aujourd'hui", "1 mois", "6 mois", "1 an", "5 ans"])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        
        map_p = {"Aujourd'hui": ("1d", "1m"), "1 mois": ("1mo", "60m"), "6 mois": ("6mo", "1d"), "1 an": ("1y", "1d"), "5 ans": ("5y", "1wk")}
        d_h = yf.download(info['Ticker'], period=map_p[per][0], interval=map_p[per][1], progress=False)
        tracer_courbe(d_h, f"{choix} ({per})", pru=info['PRU'], s_h=info.get('Seuil_Haut'), s_b=info.get('Seuil_Bas'))

with t3:
    st.subheader("Évolution de la Valeur Totale (1 mois)")
    tickers = [x['Ticker'] for x in st.session_state.mon_portefeuille]
    if tickers:
        data = yf.download(tickers, period="1mo", interval="1d", progress=False)['Close']
        if not data.empty:
            df_perf = pd.DataFrame(index=data.index)
            v_tot = pd.Series(0.0, index=data.index)
            for a in st.session_state.mon_portefeuille:
                t = a['Ticker']
                if t in data.columns: v_tot += data[t] * float(a['Qté'])
                elif len(tickers) == 1: v_tot += data * float(a['Qté'])
            df_perf['Close'] = v_tot
            tracer_courbe(df_perf, "Valeur Portefeuille (€)")

with t4:
    st.header("🔍 Watchlist")
    if st.button("➕ Ajouter une surveillance"): st.session_state.w_form = not st.session_state.get('w_form', False)
    if st.session_state.get('w_form', False):
        with st.form("wf"):
            c1, c2, c3, c4 = st.columns(4)
            wn = c1.text_input("Nom")
            wi = c2.text_input("ISIN")
            wt = c3.text_input("Ticker")
            ws = c4.number_input("Seuil", min_value=0.0)
            if st.form_submit_button("Ajouter"):
                st.session_state.ma_watchlist.append({"Nom":wn, "ISIN":wi if wi else wt.upper(), "Ticker":wt.upper(), "Seuil_Alerte":ws})
                sauvegarder_csv_github(st.session_state.ma_watchlist, "watchlist_data.csv")
                st.rerun()
    for j, w in enumerate(st.session_state.ma_watchlist):
        cw = prices.get(w['Ticker'], 0.0)
        st.write(f"**{w['Nom']}** | Prix: {cw:.2f}€ | Seuil: {w['Seuil_Alerte']:.2f}€")

with t5:
    st.header("💰 Valorisation & Dividendes")
    if st.session_state.mon_portefeuille:
        df_d = pd.DataFrame(st.session_state.mes_dividendes)
        bilan = []
        g_i, g_a, g_d = 0.0, 0.0, 0.0
        for a in st.session_state.mon_portefeuille:
            p_a = prices.get(a['Ticker'], 0.0)
            q = float(a['Qté'])
            i = float(a['PRU']) * q
            v = p_a * q
            d = df_d[df_d['Ticker'] == a['Ticker']]['Montant'].sum() if not df_d.empty else 0.0
            g_i += i; g_a += v; g_d += d
            bilan.append({"Action": a['Nom'], "Investi": round(i,2), "P/L Bourse": round(v-i,2), "Dividendes": round(d,2), "Rendement Réel": f"{((v+d-i)/i*100):+.2f}%"})
        
        bilan.append({"Action": "---", "Investi": 0, "P/L Bourse": 0, "Dividendes": 0, "Rendement Réel": "---"})
        bilan.append({"Action": "🏆 TOTAL PORTEFEUILLE", "Investi": round(g_i,2), "P/L Bourse": round(g_a-g_i,2), "Dividendes": round(g_d,2), "Rendement Réel": f"{((g_a+g_d-g_i)/g_i*100):+.2f}%"})
        st.table(pd.DataFrame(bilan))
