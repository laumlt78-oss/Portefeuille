import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import base64
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from io import StringIO
from bs4 import BeautifulSoup

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Portefeuille Expert", layout="wide", initial_sidebar_state="expanded")

try:
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
except:
    st.error("Secrets manquants dans Streamlit Cloud.")
    st.stop()

# --- 2. FONCTIONS TECHNIQUES ---
def get_fallback_price(isin):
    """ Tente de récupérer le prix sur Yahoo via scraping si l'API échoue """
    if not isin: return None
    try:
        url = f"https://finance.yahoo.com/quote/{isin}.PA"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        price_tag = soup.find('fin-streamer', {'data-field': 'regularMarketPrice'})
        return float(price_tag['value'])
    except:
        return None

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

# --- 3. RÉCUPÉRATION DES PRIX (Version Robustifiée) ---
ticker_to_isin = {x['Ticker']: x.get('ISIN') for x in st.session_state.mon_portefeuille + st.session_state.ma_watchlist}
all_tickers = list(set(ticker_to_isin.keys()))
prices = {}

if all_tickers:
    for t in all_tickers:
        p = 0.0
        try:
            # A. Tentative avec le Ticker (API standard)
            tk = yf.Ticker(t)
            hist = tk.history(period="7d")
            if not hist.empty:
                p = float(hist['Close'].iloc[-1])
            
            # B. Si échec, tentative via l'ISIN
            if (p <= 0) and ticker_to_isin.get(t):
                isin_code = ticker_to_isin[t]
                for suffix in ["", ".PA"]:
                    tk_isin = yf.Ticker(f"{isin_code}{suffix}")
                    hist_isin = tk_isin.history(period="1d")
                    if not hist_isin.empty:
                        p = float(hist_isin['Close'].iloc[-1])
                        break
            
            # C. Si toujours échec, tentative Scraping
            if (p <= 0) and ticker_to_isin.get(t):
                p = get_fallback_price(ticker_to_isin[t])
            
            # D. Ultime secours : Prix manuel enregistré
            if (p is None or p <= 0):
                for x in st.session_state.mon_portefeuille:
                    if x['Ticker'] == t:
                        p = float(x.get('Prix_Manuel', 0))
                        break
        except:
            p = 0.0
        prices[t] = float(p) if p else 0.0

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
    
    st.divider()
    with st.form("add_form", clear_on_submit=True):
        st.subheader("➕ Ajouter une Action")
        n = st.text_input("Nom de l'entreprise")
        i_code = st.text_input("Code ISIN")
        t = st.text_input("Ticker Yahoo (ex: AIR.PA)")
        p = st.number_input("PRU (€)", min_value=0.0, step=0.01)
        q = st.number_input("Quantité", min_value=0.0, step=0.1)
        d = st.date_input("Date d'Achat", value=date.today())
        
        if st.form_submit_button("Ajouter au Portefeuille"):
            if n and t:
                isin_final = i_code if i_code else t.upper()
                st.session_state.mon_portefeuille.append({
                    "Nom": n, "ISIN": isin_final, "Ticker": t.upper(), 
                    "PRU": p, "Qté": q, "Date_Achat": str(d), 
                    "Seuil_Haut": p*1.2, "Seuil_Bas": p*0.8,
                    "Prix_Manuel": 0.0
                })
                sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                st.success(f"{n} ajouté !")
                st.rerun()

# --- 6. ONGLETS ---
t1, t2, t3, t4, t5 = st.tabs(["📊 Portefeuille", "📈 Graphiques", "🌍 Performance", "🔍 Watchlist", "💰 Valorisation"])

with t1:
    for p in positions_calculees:
        a = p['act']
        icone = "🟢" if p['pv'] >= 0 else "🔴"
        pru_val = float(a.get('PRU', 0))
        s_bas_auto = float(a.get('Seuil_Bas')) if pd.notnull(a.get('Seuil_Bas')) and float(a.get('Seuil_Bas',0)) > 0 else pru_val * 0.70
        s_haut = float(a.get('Seuil_Haut', 0)) if pd.notnull(a.get('Seuil_Haut')) and float(a.get('Seuil_Haut',0)) > 0 else pru_val * 1.20
        p_pv_pct = (p['pv'] / (pru_val * p['qte']) * 100) if (pru_val * p['qte']) > 0 else 0
        
        with st.expander(f"{icone} {a['Nom']} | {p['c_act']:.2f}€ | {p['pv']:+.2f}€ ({p_pv_pct:+.2f}%)"):
            c1, c2, c3, c4 = st.columns([2, 2, 2, 1.5])
            with c1:
                st.write(f"**ISIN:** {a.get('ISIN')}")
                st.write(f"**Ticker:** {a.get('Ticker')}")
                st.write(f"**PRU Unitaire:** {pru_val:.2f}€")
            with c2:
                st.write(f"**Qté:** {p['qte']}")
                st.write(f"**Valeur Actuelle:** {p['val']:.2f}€")
            with c3:
                st.write(f"**Objectif (Haut):** {s_haut:.2f}€")
                st.write(f"**Alerte (Bas):** {s_bas_auto:.2f}€")
            
            with c4:
                col_ed, col_sel, col_del = st.columns(3)
                if col_ed.button("✏️", key=f"ed_{p['idx']}"): st.session_state[f"edit_{p['idx']}"] = True
                if col_sel.button("🛒", key=f"sell_{p['idx']}"): st.session_state[f"sell_mode_{p['idx']}"] = True
                if col_del.button("🗑️", key=f"del_{p['idx']}"):
                    st.session_state.mon_portefeuille.pop(p['idx'])
                    sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                    st.rerun()

            if st.session_state.get(f"edit_{p['idx']}", False):
                with st.form(f"f_edit_{p['idx']}"):
                    st.subheader(f"Réglages de {a['Nom']}")
                    n_pru = st.number_input("Nouveau PRU", value=pru_val)
                    n_qte = st.number_input("Nouvelle Qté", value=float(p['qte']))
                    n_sh = st.number_input("Seuil Haut", value=s_haut)
                    n_sb = st.number_input("Seuil Bas", value=s_bas_auto)
                    
                    st.divider()
                    st.write("⚠️ **Correction manuelle du prix**")
                    val_man_init = float(a.get('Prix_Manuel', 0))
                    n_prix_man = st.number_input("Forcer le prix de la part (€)", value=val_man_init, help="Saisir la VL si Yahoo est KO")
                    
                    if st.form_submit_button("Valider"):
                        st.session_state.mon_portefeuille[p['idx']].update({
                            "PRU": n_pru, "Qté": n_qte, "Seuil_Haut": n_sh, "Seuil_Bas": n_sb, "Prix_Manuel": n_prix_man
                        })
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
        
        # Tentative intelligente pour le graphique
        d_h = yf.download(info['Ticker'], period=map_p[per][0], interval=map_p[per][1], progress=False)
        if (d_h is None or d_h.empty) and info.get('ISIN'):
            for code in [info['ISIN'], f"{info['ISIN']}.PA"]:
                d_h = yf.download(code, period=map_p[per][0], interval=map_p[per][1], progress=False)
                if not d_h.empty: break
        
        tracer_courbe(d_h, f"{choix} ({per})", pru=info['PRU'], s_h=info.get('Seuil_Haut'), s_b=info.get('Seuil_Bas'))

# ... (Les autres onglets t3, t4, t5 restent identiques à votre version précédente)
