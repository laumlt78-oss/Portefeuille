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

# Initialisation des sessions
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
    for t in all_tickers:
        try:
            tk = yf.Ticker(t)
            price = tk.fast_info.last_price
            if price is None or price == 0:
                price = tk.history(period="1d")['Close'].iloc[-1]
            prices[t] = float(price)
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
            "pv": val_titre - (pru * qte), "pru": pru, "qte": qte
        })
    except: continue

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("💰 Résumé")
    if total_achat > 0:
        st.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        st.metric("P/L GLOBAL", f"{(total_actuel-total_achat):+.2f} €", delta=f"{((total_actuel-total_achat)/total_achat*100):+.2f}%")
    st.divider()
    with st.form("add_form", clear_on_submit=True):
        st.subheader("➕ Ajouter")
        n, i_code, t = st.text_input("Nom"), st.text_input("ISIN"), st.text_input("Ticker")
        p, q = st.number_input("PRU", min_value=0.0), st.number_input("Qté", min_value=0.0)
        d = st.date_input("Date Achat", value=date.today())
        if st.form_submit_button("Ajouter"):
            if n and t:
                isin_final = i_code if i_code else t.upper() # Remplissage auto ISIN
                st.session_state.mon_portefeuille.append({"Nom":n, "ISIN":isin_final, "Ticker":t.upper(), "PRU":p, "Qté":q, "Date_Achat":str(d), "Seuil_Haut":0, "Seuil_Bas":p*0.7})
                sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                st.rerun()

# --- 6. ONGLET ---
t1, t2, t3, t4, t5 = st.tabs(["📊 Portefeuille", "📈 Graphiques", "🌍 Performance", "🔍 Watchlist", "💰 Valorisation"])

with t1:
    for p in positions_calculees:
        a = p['act']
        header = f"{a['Nom']} | {p['c_act']:.2f}€ | {p['pv']:+.2f}€"
        with st.expander(header):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1])
            with c1:
                st.write(f"**ISIN:** {a.get('ISIN')}")
                st.write(f"**PRU Unitaire:** {p['pru']:.2f}€")
            with c2:
                st.write(f"**Qté:** {p['qte']}")
                st.write(f"**Valeur:** {p['val']:.2f}€")
            with c4:
                if st.button("✏️", key=f"edit_{p['idx']}"):
                    st.session_state[f"editing_{p['idx']}"] = True
                if st.button("🗑️", key=f"del_{p['idx']}"):
                    st.session_state.mon_portefeuille.pop(p['idx'])
                    sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                    st.rerun()
            
            if st.session_state.get(f"editing_{p['idx']}", False):
                with st.form(f"f_edit_{p['idx']}"):
                    new_pru = st.number_input("PRU", value=p['pru'])
                    new_qte = st.number_input("Qté", value=p['qte'])
                    if st.form_submit_button("Valider"):
                        st.session_state.mon_portefeuille[p['idx']].update({"PRU": new_pru, "Qté": new_qte})
                        sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                        st.session_state[f"editing_{p['idx']}"] = False
                        st.rerun()

with t2:
    if st.session_state.mon_portefeuille:
        choix = st.selectbox("Action", [x['Nom'] for x in st.session_state.mon_portefeuille])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        df_h = yf.download(info['Ticker'], period="1y", progress=False)
        tracer_courbe(df_h, info['Nom'], pru=info['PRU'])

with t4: # Watchlist Corrigée
    st.header("🔍 Valeurs à surveiller")
    if st.button("➕ Ajouter une surveillance"):
        st.session_state.show_w_form = not st.session_state.get('show_w_form', False)
    
    if st.session_state.get('show_w_form', False):
        c1, c2, c3 = st.columns(3)
        wn = c1.text_input("Nom")
        wi = c2.text_input("ISIN (Vide = Ticker)")
        wt = c3.text_input("Ticker")
        ws = st.number_input("Seuil d'alerte", min_value=0.0)
        if st.button("Lancer la surveillance"):
            if wn and wt:
                isin_w = wi if wi else wt.upper()
                st.session_state.ma_watchlist.append({"Nom": wn, "ISIN": isin_w, "Ticker": wt.upper(), "Seuil_Alerte": ws})
                sauvegarder_csv_github(st.session_state.ma_watchlist, "watchlist_data.csv")
                st.session_state.show_w_form = False
                st.rerun()

    for j, w in enumerate(st.session_state.ma_watchlist):
        cur_w = prices.get(w['Ticker'], 0.0)
        st.write(f"**{w['Nom']}** | Cours: {cur_w:.2f}€ | Seuil: {w['Seuil_Alerte']:.2f}€")

with t5: # Valorisation avec Ligne Portefeuille
    st.header("💰 Valorisation Réelle")
    if st.session_state.mon_portefeuille:
        df_div = pd.DataFrame(st.session_state.mes_dividendes)
        bilan_data = []
        g_investi, g_actuel, g_div = 0.0, 0.0, 0.0

        for a in st.session_state.mon_portefeuille:
            p_act = prices.get(a['Ticker'], 0.0)
            qte = float(a['Qté'])
            investi = float(a['PRU']) * qte
            val_act = p_act * qte
            s_div = df_div[df_div['Ticker'] == a['Ticker']]['Montant'].sum() if not df_div.empty else 0.0
            
            g_investi += investi ; g_actuel += val_act ; g_div += s_div
            
            bilan_data.append({
                "Action": a['Nom'], "Investi": round(investi, 2),
                "P/L Bourse": round(val_act - investi, 2), "Dividendes": round(s_div, 2),
                "Rendement Réel": f"{((val_act + s_div - investi)/investi*100):+.2f}%" if investi > 0 else "0%"
            })
        
        # Ajout de la ligne PORTEFEUILLE
        bilan_data.append({
            "Action": "---", "Investi": "---", "P/L Bourse": "---", "Dividendes": "---", "Rendement Réel": "---"
        })
        bilan_data.append({
            "Action": "🏆 PORTEFEUILLE", "Investi": round(g_investi, 2),
            "P/L Bourse": round(g_actuel - g_investi, 2), "Dividendes": round(g_div, 2),
            "Rendement Réel": f"{((g_actuel + g_div - g_investi)/g_investi*100):+.2f}%" if g_investi > 0 else "0%"
        })
        st.table(pd.DataFrame(bilan_data))
