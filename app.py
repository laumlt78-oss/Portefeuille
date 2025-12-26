
import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import plotly.graph_objects as go
from datetime import date
from requests.exceptions import RequestException, Timeout

# --- 1. CONFIGURATION SÉCURISÉE (SECRETS) ---
try:
    USER_KEY = st.secrets["PUSHOVER_USER_KEY"]
    API_TOKEN = st.secrets["PUSHOVER_API_TOKEN"]
except KeyError:
    st.error("Clés Pushover manquantes dans .streamlit/secrets.toml")
    USER_KEY, API_TOKEN = None, None

def envoyer_alerte(message):
    if not USER_KEY or not API_TOKEN:
        return
    try:
        response = requests.post("https://api.pushover.net/1/messages.json", data={
            "token": API_TOKEN, "user": USER_KEY, "message": message
        }, timeout=5)
        response.raise_for_status()
    except (Timeout, RequestException):
        pass # Évite de bloquer l'app si le réseau flanche

st.set_page_config(page_title="Portefeuille Pro Sécurisé", layout="wide")

# --- 2. GESTION ROBUSTE DES DONNÉES ---
FICHIER_DATA = "portefeuille_data.csv"
COLS_VALIDEES = ['Nom', 'ISIN', 'Ticker', 'PRU', 'Qté', 'Seuil_Haut', 'Date_Achat']

def charger_donnees():
    if not os.path.exists(FICHIER_DATA) or os.path.getsize(FICHIER_DATA) == 0:
        return []
    try:
        # On ne lit que les colonnes autorisées
        df = pd.read_csv(FICHIER_DATA)
        df = df[[c for c in COLS_VALIDEES if c in df.columns]]
        df = df.fillna("")
        
        # Validation des types
        if 'PRU' in df.columns: df['PRU'] = pd.to_numeric(df['PRU'], errors='coerce').fillna(0.0)
        if 'Qté' in df.columns: df['Qté'] = pd.to_numeric(df['Qté'], errors='coerce').fillna(0).astype(int)
        
        # Ajout des colonnes manquantes
        for col in COLS_VALIDEES:
            if col not in df.columns:
                df[col] = "" if col in ['ISIN', 'Nom', 'Ticker'] else (0.0 if col != 'Date_Achat' else str(date.today()))
        
        return df.to_dict('records')
    except Exception as e:
        st.error(f"Erreur lors de la lecture du fichier : {e}")
        return []

def sauvegarder_donnees(liste):
    try:
        if liste:
            pd.DataFrame(liste).to_csv(FICHIER_DATA, index=False)
        elif os.path.exists(FICHIER_DATA):
            os.remove(FICHIER_DATA)
    except IOError as e:
        st.error(f"Impossible de sauvegarder : {e}")

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_donnees()

# --- 3. GRAPHIQUES ---
def tracer_graphe(ticker, p, label):
    try:
        data = yf.download(ticker, period=p, interval="15m" if p=="1d" else "1d", progress=False)
        if not data.empty:
            fig = go.Figure(data=[go.Scatter(x=data.index, y=data['Close'], line=dict(color='#00FF00', width=2))])
            fig.update_layout(title=f"{label} - {ticker}", height=250, template="plotly_dark", margin=dict(l=10,r=10,t=40,b=10))
            st.plotly_chart(fig, use_container_width=True, key=f"g_{ticker}_{p}")
    except Exception:
        st.warning(f"Impossible de charger le graphique pour {ticker}")

# --- 4. NAVIGATION ---
tab_p, tab_g = st.tabs(["📊 Portefeuille", "📈 Graphes"])

# --- 5. CALCULS ---
if st.session_state.mon_portefeuille:
    total_actuel, total_achat, var_jour = 0.0, 0.0, 0.0
    donnees_pos = []

    for i, act in enumerate(st.session_state.mon_portefeuille):
        try:
            t = yf.Ticker(act['Ticker'])
            h = t.history(period="2d")
            if not h.empty:
                p_act = h['Close'].iloc[-1]
                p_prev = h['Close'].iloc[-2] if len(h) > 1 else p_act
                v_act = p_act * act['Qté']
                total_actuel += v_act
                total_achat += (float(act['PRU']) * int(act['Qté']))
                var_jour += (p_act - p_prev) * int(act['Qté'])
                donnees_pos.append({"idx": i, "act": act, "prix": p_act, "var": (p_act - p_prev) * int(act['Qté']), "val": v_act})
                
                # Alertes Pushover
                if p_act > 0:
                    if p_act <= (float(act['PRU']) * 0.80):
                        envoyer_alerte(f"🚨 BAS : {act['Nom']} ({p_act:.2f}€)")
                    if float(act.get('Seuil_Haut', 0)) > 0 and p_act >= float(act['Seuil_Haut']):
                        envoyer_alerte(f"🎯 OBJECTIF : {act['Nom']} ({p_act:.2f}€)")
        except Exception: pass

    with tab_p:
        pv_g = total_actuel - total_achat
        c1, c2, c3 = st.columns(3)
        c1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        c2.metric("P/L GLOBAL", f"{pv_g:.2f} €", delta=f"{(pv_g/total_achat*100 if total_achat>0 else 0):+.2f} %")
        c3.metric("VAR. JOUR", f"{var_jour:+.2f} €")
        st.divider()

        for item in donnees_pos:
            idx, a, p = item['idx'], item['act'], item['prix']
            pv_l = (p - float(a['PRU'])) * int(a['Qté'])
            val_isin = str(a.get('ISIN', '')).strip()
            header = f"{'🟢' if pv_l >= 0 else '🔴'} {a['Nom']} | {p:.2f}€ | {pv_l:+.2f}€ | {val_isin}"
            
            with st.expander(header):
                edit_mode = st.toggle("📝 Modifier", key=f"edit_{idx}")
                if edit_mode:
                    with st.form(f"f_edit_{idx}"):
                        c_e1, c_e2 = st.columns(2)
                        n_nom = c_e1.text_input("Nom", value=a['Nom'])
                        n_isin = c_e2.text_input("ISIN", value=val_isin)
                        n_pru = c_e1.number_input("PRU", value=float(a['PRU']), min_value=0.0)
                        n_qte = c_e2.number_input("Qté", value=int(a['Qté']), min_value=1)
                        n_obj = c_e1.number_input("Objectif", value=float(a.get('Seuil_Haut', 0.0)))
                        n_date = c_e2.date_input("Date", value=pd.to_datetime(a.get('Date_Achat', date.today())))
                        if st.form_submit_button("Sauvegarder"):
                            st.session_state.mon_portefeuille[idx].update({
                                "Nom": n_nom, "ISIN": n_isin, "PRU": n_pru, "Qté": n_qte, "Seuil_Haut": n_obj, "Date_Achat": str(n_date)
                            })
                            sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()
                else:
                    st.write(f"**ISIN :** {val_isin} | **Date :** {a.get('Date_Achat')}")
                    if st.button("🗑️ Supprimer", key=f"del_{idx}"):
                        st.session_state.mon_portefeuille.pop(idx)
                        sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()

    with tab_g:
        noms = [x['Nom'] for x in st.session_state.mon_portefeuille]
        if noms:
            choix = st.selectbox("Action :", noms)
            t_sel = next(x['Ticker'] for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
            tracer_graphe(t_sel, "1y", "Année")

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("🔍 Ajouter un Titre")
    q = st.text_input("Recherche Nom/ISIN")
    t_sug, n_sug = "", ""
    if q:
        try:
            res = yf.Search(q, max_results=3).quotes
            if res:
                opts = {f"{r['shortname']} ({r['symbol']})": r['symbol'] for r in res}
                s = st.selectbox("Résultats :", opts.keys())
                t_sug, n_sug = opts[s], s.split(' (')[0]
        except Exception: pass

    with st.form("add_f", clear_on_submit=True):
        f_n = st.text_input("Nom", value=n_sug)
        f_isin = st.text_input("Code ISIN")
        f_t = st.text_input("Ticker", value=t_sug)
        f_p = st.number_input("PRU", min_value=0.0)
        f_q = st.number_input("Quantité", min_value=1)
        f_h = st.number_input("Objectif", min_value=0.0)
        f_d = st.date_input("Date d'achat", value=date.today())
        if st.form_submit_button("Ajouter"):
            if not f_t or not f_n:
                st.error("Nom et Ticker requis.")
            else:
                st.session_state.mon_portefeuille.append({
                    "Nom": f_n, "ISIN": f_isin, "Ticker": f_t.upper(), "PRU": f_p, 
                    "Qté": f_q, "Seuil_Haut": f_h, "Date_Achat": str(f_d)
                })
                sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()

    st.divider()
    st.subheader("⚙️ Maintenance")
    up = st.file_uploader("📤 Restaurer CSV", type="csv")
    if up:
        try:
            st.session_state.mon_portefeuille = pd.read_csv(up).to_dict('records')
            sauvegarder_donnees(st.session_state.mon_portefeuille)
            st.success("Données restaurées !")
            st.button("Rafraîchir")
        except Exception: st.error("Fichier corrompu.")
    
    df_b = pd.DataFrame(st.session_state.mon_portefeuille)
    st.download_button("📥 Backup CSV", df_b.to_csv(index=False).encode('utf-8'), "portefeuille.csv", use_container_width=True)




