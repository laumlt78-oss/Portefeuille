
import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import plotly.graph_objects as go
from datetime import date

# --- 1. CONFIGURATION PUSHOVER ---
# Remplacez par vos vraies clés Pushover
USER_KEY = "uy24daw7gs19ivfhwh7wgsy8amajc8"
API_TOKEN = "a2d5he9d9idw5e4rkoapym7kwfs9ha"

def envoyer_alerte(message):
    if USER_KEY != "VOTRE_USER_KEY_ICI":
        try:
            requests.post("https://api.pushover.net/1/messages.json", data={
                "token": API_TOKEN, 
                "user": USER_KEY, 
                "message": message
            }, timeout=5)
        except:
            pass

st.set_page_config(page_title="Mon Portefeuille Pro", layout="wide")

# --- 2. GESTION DES DONNÉES ---
FICHIER_DATA = "portefeuille_data.csv"

def charger_donnees():
    if not os.path.exists(FICHIER_DATA) or os.path.getsize(FICHIER_DATA) == 0:
        return []
    try:
        df = pd.read_csv(FICHIER_DATA)
        # Gestion des colonnes manquantes lors d'imports de vieux fichiers
        if 'Date_Achat' not in df.columns: df['Date_Achat'] = str(date.today())
        if 'Seuil_Haut' not in df.columns: df['Seuil_Haut'] = 0.0
        return df.to_dict('records')
    except:
        return []

def sauvegarder_donnees(liste):
    if liste:
        pd.DataFrame(liste).to_csv(FICHIER_DATA, index=False)
    elif os.path.exists(FICHIER_DATA):
        os.remove(FICHIER_DATA)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_donnees()

# --- 3. FONCTION GRAPHIQUE ---
def tracer_graphe(ticker, p, label):
    try:
        data = yf.download(ticker, period=p, interval="15m" if p=="1d" else "1d", progress=False)
        if not data.empty:
            fig = go.Figure(data=[go.Scatter(x=data.index, y=data['Close'], line=dict(color='#00FF00', width=2))])
            fig.update_layout(title=f"{label} - {ticker}", height=250, template="plotly_dark", margin=dict(l=10,r=10,t=40,b=10))
            st.plotly_chart(fig, use_container_width=True, key=f"g_{ticker}_{p}")
    except:
        st.error(f"Erreur de chargement pour {label}")

# --- 4. NAVIGATION ---
tab_p, tab_g = st.tabs(["📊 Portefeuille", "📈 Graphes"])

# --- 5. CALCULS ---
if st.session_state.mon_portefeuille:
    total_actuel, total_achat, var_jour = 0, 0, 0
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
                
                # --- LOGIQUE ALERTES PUSHOVER ---
                if p_act > 0:
                    seuil_bas = float(act['PRU']) * 0.80
                    if p_act <= seuil_bas:
                        envoyer_alerte(f"🚨 ALERTE BASSE : {act['Nom']} est à {p_act:.2f}€ (PRU: {act['PRU']}€)")
                    if float(act.get('Seuil_Haut', 0)) > 0 and p_act >= float(act['Seuil_Haut']):
                        envoyer_alerte(f"🎯 OBJECTIF ATTEINT : {act['Nom']} est à {p_act:.2f}€")
        except:
            pass

    # --- ONGLET PORTEFEUILLE ---
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
            header = f"{'🟢' if pv_l >= 0 else '🔴'} {a['Nom']} | {p:.2f}€ | {pv_l:+.2f}€"
            
            with st.expander(header):
                edit_mode = st.toggle("📝 Modifier cette ligne", key=f"edit_{idx}")
                
                if edit_mode:
                    with st.form(f"f_edit_{idx}"):
                        col_e1, col_e2 = st.columns(2)
                        n_pru = col_e1.number_input("PRU", value=float(a['PRU']), format="%.2f")
                        n_qte = col_e2.number_input("Quantité", value=int(a['Qté']), min_value=1)
                        n_obj = col_e1.number_input("Objectif", value=float(a.get('Seuil_Haut', 0.0)))
                        n_date = col_e2.date_input("Date achat", value=pd.to_datetime(a.get('Date_Achat', date.today())))
                        
                        if st.form_submit_button("Sauvegarder"):
                            st.session_state.mon_portefeuille[idx].update({
                                "PRU": n_pru, "Qté": n_qte, "Seuil_Haut": n_obj, "Date_Achat": str(n_date)
                            })
                            sauvegarder_donnees(st.session_state.mon_portefeuille)
                            st.rerun()
                else:
                    st.write(f"**Quantité :** {a['Qté']} | **PRU :** {a['PRU']:.2f}€ | **Date d'achat :** {a.get('Date_Achat', 'N/C')}")
                    st.write(f"**Valeur actuelle :** {item['val']:.2f}€ | **Var. Jour :** {item['var']:+.2f}€ | **Objectif :** {a.get('Seuil_Haut', 0)}€")
                    if st.button("🗑️ Supprimer", key=f"del_{idx}"):
                        st.session_state.mon_portefeuille.pop(idx)
                        sauvegarder_donnees(st.session_state.mon_portefeuille)
                        st.rerun()

    # --- ONGLET GRAPHES ---
    with tab_g:
        noms = [x['Nom'] for x in st.session_state.mon_portefeuille]
        if noms:
            choix = st.selectbox("Sélectionner une action :", noms)
            t_sel = next(x['Ticker'] for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
            for p, l in [("1d","Aujourd'hui"), ("5d","Semaine"), ("1mo","Mois"), ("1y","Année"), ("max","Max")]:
                tracer_graphe(t_sel, p, l)

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header("🔍 Ajouter un Titre")
    q = st.text_input("Nom ou ISIN")
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
        f_t = st.text_input("Ticker", value=t_sug)
        f_p = st.number_input("PRU", min_value=0.0, format="%.2f")
        f_q = st.number_input("Quantité", min_value=1)
        f_h = st.number_input("Objectif Vente", min_value=0.0)
        f_d = st.date_input("Date d'achat", value=date.today())
        if st.form_submit_button("Ajouter au Portefeuille"):
            if f_t:
                st.session_state.mon_portefeuille.append({
                    "Nom": f_n, "Ticker": f_t.upper(), "PRU": f_p, 
                    "Qté": f_q, "Seuil_Haut": f_h, "Date_Achat": str(f_d)
                })
                sauvegarder_donnees(st.session_state.mon_portefeuille)
                st.rerun()

    st.divider()
    st.header("💾 Maintenance")
    df_b = pd.DataFrame(st.session_state.mon_portefeuille)
    st.download_button("📥 Télécharger Backup", df_b.to_csv(index=False).encode('utf-8'), "mon_portefeuille.csv", use_container_width=True)
    up = st.file_uploader("📤 Restaurer CSV", type="csv")
    if up:
        st.session_state.mon_portefeuille = pd.read_csv(up).to_dict('records')
        sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()
