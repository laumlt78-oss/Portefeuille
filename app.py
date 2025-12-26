import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import plotly.graph_objects as go
from datetime import date
from requests.exceptions import RequestException, Timeout

# --- 1. CONFIGURATION SÉCURISÉE ---
try:
    USER_KEY = st.secrets["PUSHOVER_USER_KEY"]
    API_TOKEN = st.secrets["PUSHOVER_API_TOKEN"]
except:
    USER_KEY, API_TOKEN = None, None

def envoyer_alerte(message):
    if not USER_KEY or not API_TOKEN: return
    try:
        requests.post("https://api.pushover.net/1/messages.json", data={
            "token": API_TOKEN, "user": USER_KEY, "message": message
        }, timeout=5)
    except: pass

st.set_page_config(page_title="Portefeuille Pro", layout="wide")

# --- 2. GESTION DES DONNÉES ---
FICHIER_DATA = "portefeuille_data.csv"
COLS_VALIDEES = ['Nom', 'ISIN', 'Ticker', 'PRU', 'Qté', 'Seuil_Haut', 'Date_Achat']

def charger_donnees():
    if not os.path.exists(FICHIER_DATA) or os.path.getsize(FICHIER_DATA) == 0:
        return []
    try:
        df = pd.read_csv(FICHIER_DATA)
        df = df.fillna("")
        for col in COLS_VALIDEES:
            if col not in df.columns:
                df[col] = "" if col in ['ISIN', 'Nom', 'Ticker'] else 0.0
        return df.to_dict('records')
    except: return []

def sauvegarder_donnees(liste):
    pd.DataFrame(liste).to_csv(FICHIER_DATA, index=False)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_donnees()

# --- 3. NAVIGATION ---
tab_p, tab_g = st.tabs(["📊 Portefeuille", "📈 Graphes"])

# --- 4. CALCULS ET AFFICHAGE ---
if st.session_state.mon_portefeuille:
    total_actuel, total_achat, var_jour = 0.0, 0.0, 0.0
    donnees_pos = []

    # Premier passage pour calculer le total (nécessaire pour le poids %)
    for i, act in enumerate(st.session_state.mon_portefeuille):
        try:
            t = yf.Ticker(act['Ticker'])
            h = t.history(period="2d")
            if not h.empty:
                p_act = h['Close'].iloc[-1]
                p_prev = h['Close'].iloc[-2] if len(h) > 1 else p_act
                v_act = p_act * float(act['Qté'])
                total_actuel += v_act
                total_achat += (float(act['PRU']) * int(act['Qté']))
                var_jour += (p_act - p_prev) * int(act['Qté'])
                donnees_pos.append({"idx": i, "act": act, "prix": p_act, "var": (p_act - p_prev) * int(act['Qté']), "val": v_act})
        except: pass

    with tab_p:
        # Metrics Globales
        pv_g = total_actuel - total_achat
        c1, c2, c3 = st.columns(3)
        c1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        c2.metric("P/L GLOBAL", f"{pv_g:.2f} €", delta=f"{(pv_g/total_achat*100 if total_achat>0 else 0):+.2f} %")
        c3.metric("VAR. JOUR", f"{var_jour:+.2f} €")
        st.divider()

        # Liste des actions
        for item in donnees_pos:
            idx, a, p = item['idx'], item['act'], item['prix']
            pru, qte = float(a['PRU']), int(a['Qté'])
            val_ligne = item['val']
            pv_l = (p - pru) * qte
            pv_pente = ((p - pru) / pru * 100) if pru > 0 else 0
            poids = (val_ligne / total_actuel * 100) if total_actuel > 0 else 0
            obj = float(a.get('Seuil_Haut', 0.0))
            val_isin = str(a.get('ISIN', '')).strip()

            header = f"{'🟢' if pv_l >= 0 else '🔴'} {a['Nom']} | {p:.2f}€ | {pv_l:+.2f}€ ({pv_pente:+.2f}%) | {val_isin}"
            
            with st.expander(header):
                edit_mode = st.toggle("📝 Modifier", key=f"ed_{idx}")
                if edit_mode:
                    with st.form(f"f_{idx}"):
                        ce1, ce2 = st.columns(2)
                        n_nom = ce1.text_input("Nom", value=a['Nom'])
                        n_isin = ce2.text_input("ISIN", value=val_isin)
                        n_pru = ce1.number_input("PRU", value=pru)
                        n_qte = ce2.number_input("Qté", value=qte, min_value=1)
                        n_obj = ce1.number_input("Objectif", value=obj)
                        n_date = ce2.date_input("Date", value=pd.to_datetime(a.get('Date_Achat', date.today())))
                        if st.form_submit_button("Sauvegarder"):
                            st.session_state.mon_portefeuille[idx].update({
                                "Nom": n_nom, "ISIN": n_isin, "PRU": n_pru, "Qté": n_qte, "Seuil_Haut": n_obj, "Date_Achat": str(n_date)
                            })
                            sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()
                else:
                    c_i1, c_i2, c_i3 = st.columns(3)
                    c_i1.write(f"**Qté :** {qte} | **PRU :** {pru:.2f}€")
                    c_i1.write(f"**Poids :** {poids:.2f}%")
                    c_i2.write(f"**Valeur :** {val_ligne:.2f}€")
                    c_i2.write(f"**P/L :** {pv_l:+.2f}€ ({pv_pente:+.2f}%)")
                    c_i3.write(f"**Objectif :** {obj:.2f}€")
                    dist = ((obj-p)/p*100) if p>0 and obj>0 else 0
                    c_i3.write(f"**Dist. Obj :** {dist:+.2f}%")
                    if st.button("🗑️ Supprimer", key=f"del_{idx}"):
                        st.session_state.mon_portefeuille.pop(idx)
                        sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()

    with tab_g:
        noms = [x['Nom'] for x in st.session_state.mon_portefeuille]
        if noms:
            choix = st.selectbox("Choisir une action :", noms)
            t_sel = next(x['Ticker'] for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
            d = yf.download(t_sel, period="1y", progress=False)
            if not d.empty:
                fig = go.Figure(data=[go.Scatter(x=d.index, y=d['Close'], line=dict(color='#00FF00'))])
                fig.update_layout(template="plotly_dark", title=f"Historique 1 an : {t_sel}")
                st.plotly_chart(fig, use_container_width=True)

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header("🔍 Ajouter un Titre")
    q = st.text_input("Recherche (Nom/ISIN)")
    t_sug, n_sug = "", ""
    if q:
        try:
            res = yf.Search(q, max_results=3).quotes
            if res:
                opts = {f"{r['shortname']} ({r['symbol']})": r['symbol'] for r in res}
                s = st.selectbox("Résultats :", opts.keys())
                t_sug, n_sug = opts[s], s.split(' (')[0]
        except: pass

    with st.form("add_f", clear_on_submit=True):
        f_n = st.text_input("Nom", value=n_sug)
        f_isin = st.text_input("ISIN")
        f_t = st.text_input("Ticker", value=t_sug)
        f_p = st.number_input("PRU", min_value=0.0)
        f_q = st.number_input("Quantité", min_value=1)
        f_h = st.number_input("Objectif", min_value=0.0)
        f_d = st.date_input("Date", value=date.today())
        if st.form_submit_button("Ajouter"):
            if f_t and f_n:
                st.session_state.mon_portefeuille.append({
                    "Nom": f_n, "ISIN": f_isin, "Ticker": f_t.upper(), "PRU": f_p, 
                    "Qté": f_q, "Seuil_Haut": f_h, "Date_Achat": str(f_d)
                })
                sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()

    st.divider()
    st.subheader("⚙️ Maintenance")
    up = st.file_uploader("📤 Restaurer CSV", type="csv")
    if up:
        st.session_state.mon_portefeuille = pd.read_csv(up).to_dict('records')
        sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()
    
    df_b = pd.DataFrame(st.session_state.mon_portefeuille)
    st.download_button("📥 Backup CSV", df_b.to_csv(index=False).encode('utf-8'), "portefeuille.csv")
