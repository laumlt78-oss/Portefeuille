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

with t3:
    st.subheader("📈 Évolution Portefeuille (1 mois)")
    # On récupère les tickers valides (ceux qui ne sont pas à 0)
    tickers_valides = [x['Ticker'] for x in st.session_state.mon_portefeuille if prices.get(x['Ticker'], 0) > 0]
    
    if tickers_valides:
        try:
            data = yf.download(tickers_valides, period="1mo", interval="1d", progress=False)['Close']
            if not data.empty:
                # Création d'une série temporelle vide à la taille des données reçues
                v_tot = pd.Series(0.0, index=data.index)
                for a in st.session_state.mon_portefeuille:
                    t = a['Ticker']
                    q = float(a['Qté'])
                    if isinstance(data, pd.DataFrame) and t in data.columns:
                        v_tot += data[t] * q
                    elif isinstance(data, pd.Series): # Si un seul ticker valide
                        v_tot += data * q
                    else:
                        # Si ticker non trouvé dans l'historique (ex: OPCVM), on utilise le prix actuel constant
                        v_tot += prices.get(t, 0) * q
                
                tracer_courbe(pd.DataFrame({'Close': v_tot}), "Valeur Totale du Portefeuille (€)")
        except Exception as e:
            st.error(f"Erreur lors du calcul de la performance : {e}")
    else:
        st.info("Ajoutez des valeurs avec des tickers valides pour voir l'évolution.")

with t4:
    st.header("🔍 Valeurs à surveiller (Watchlist)")
    
    if 'form_actif' not in st.session_state:
        st.session_state.form_actif = None

    if st.button("➕ Ajouter une nouvelle surveillance"): 
        st.session_state.w_form = not st.session_state.get('w_form', False)
    
    if st.session_state.get('w_form', False):
        with st.form("wf"):
            st.subheader("Nouvelle alerte")
            c1, c2, c3, c4 = st.columns(4)
            wn = c1.text_input("Nom de la valeur")
            wi = c2.text_input("ISIN (Optionnel)")
            wt = c3.text_input("Ticker Yahoo")
            ws = c4.number_input("Seuil d'Alerte (€)", min_value=0.0, step=0.01)
            
            if st.form_submit_button("Lancer la surveillance"):
                if wn and wt:
                    isin_w = wi if wi else wt.upper()
                    st.session_state.ma_watchlist.append({
                        "Nom": wn, "ISIN": isin_w, "Ticker": wt.upper(), "Seuil_Alerte": ws
                    })
                    sauvegarder_csv_github(st.session_state.ma_watchlist, "watchlist_data.csv")
                    st.session_state.w_form = False
                    st.rerun()

    st.divider()
    
    if not st.session_state.ma_watchlist:
        st.info("Votre watchlist est vide.")
    else:
        for j, w in enumerate(st.session_state.ma_watchlist):
            cw = prices.get(w['Ticker'], 0.0)
            col1, col2, col3, col_btn = st.columns([3, 2, 2, 3.5])
            col1.write(f"**{w['Nom']}** ({w['Ticker']})")
            col2.write(f"Cours: {cw:.2f}€")
            col3.write(f"Cible: {w.get('Seuil_Alerte', 0):.2f}€")
            
            c_buy, c_edit, c_del = col_btn.columns(3)
            if c_buy.button("📥", key=f"btn_buy_{j}"): st.session_state.form_actif = ("buying", j)
            if c_edit.button("✏️", key=f"btn_edit_{j}"): st.session_state.form_actif = ("editing", j)
            if c_del.button("🗑️", key=f"btn_del_{j}"):
                st.session_state.ma_watchlist.pop(j)
                sauvegarder_csv_github(st.session_state.ma_watchlist, "watchlist_data.csv")
                st.rerun()

            # Formulaire de transfert (Achat) simplifié
            if st.session_state.get('form_actif') == ("buying", j):
                with st.form(f"f_trans_{j}"):
                    st.subheader(f"📥 Acheter {w['Nom']}")
                    fb_q = st.number_input("Quantité", min_value=0.1, step=0.1)
                    fb_p = st.number_input("PRU (€)", value=cw)
                    if st.form_submit_button("Confirmer l'achat"):
                        st.session_state.mon_portefeuille.append({
                            "Nom": w['Nom'], "ISIN": w['ISIN'], "Ticker": w['Ticker'],
                            "PRU": fb_p, "Qté": fb_q, "Date_Achat": str(date.today()),
                            "Seuil_Haut": fb_p*1.2, "Seuil_Bas": fb_p*0.8, "Prix_Manuel": 0.0
                        })
                        st.session_state.ma_watchlist.pop(j)
                        sauvegarder_csv_github(st.session_state.mon_portefeuille, "portefeuille_data.csv")
                        sauvegarder_csv_github(st.session_state.ma_watchlist, "watchlist_data.csv")
                        st.session_state.form_actif = None
                        st.rerun()

with t5:
    st.header("💰 Valorisation & Dividendes")
    
    # Section Ajout Dividende
    with st.expander("➕ Déclarer un dividende"):
        with st.form("div_f"):
            dt = st.selectbox("Action", [x['Ticker'] for x in st.session_state.mon_portefeuille])
            dm = st.number_input("Montant Net (€)", min_value=0.01)
            if st.form_submit_button("Enregistrer"):
                st.session_state.mes_dividendes.append({"Ticker":dt, "Date":str(date.today()), "Montant":dm})
                sauvegarder_csv_github(st.session_state.mes_dividendes, "dividendes_data.csv")
                st.rerun()

    # Affichage du Tableau de Valorisation
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
            
            g_i += i
            g_a += v
            g_d += d
            
            bilan.append({
                "Action": a['Nom'],
                "Investi": round(i, 2),
                "P/L Bourse": round(v - i, 2),
                "Dividendes": round(d, 2),
                "Rendement Réel": f"{((v + d - i) / i * 100 if i > 0 else 0):+.2f}%"
            })
        
        # Ligne de Total
        bilan.append({
            "Action": "🏆 TOTAL PORTEFEUILLE",
            "Investi": round(g_i, 2),
            "P/L Bourse": round(g_a - g_i, 2),
            "Dividendes": round(g_d, 2),
            "Rendement Réel": f"{((g_a + g_d - g_i) / g_i * 100 if g_i > 0 else 0):+.2f}%"
        })
        
        st.table(pd.DataFrame(bilan))
    else:
        st.info("Portefeuille vide.")
