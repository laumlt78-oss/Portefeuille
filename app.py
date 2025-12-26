
import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import plotly.graph_objects as go

# --- 1. CONFIGURATION PUSHOVER ---
USER_KEY = "uy24daw7gs19ivfhwh7wgsy8amajc8"
API_TOKEN = "a2d5he9d9idw5e4rkoapym7kwfs9ha"



def envoyer_alerte(message):
    if USER_KEY != "VOTRE_USER_KEY_ICI":
        try:
            requests.post("https://api.pushover.net/1/messages.json", data={
                "token": API_TOKEN, "user": USER_KEY, "message": message
            }, timeout=5)
        except: pass

st.set_page_config(page_title="Mon Portefeuille Pro", layout="wide")

# --- 2. GESTION DES DONNÉES ---
FICHIER_DATA = "portefeuille_data.csv"

def charger_donnees():
    if not os.path.exists(FICHIER_DATA) or os.path.getsize(FICHIER_DATA) == 0:
        return []
    try:
        df = pd.read_csv(FICHIER_DATA)
        return df.to_dict('records')
    except: return []

def sauvegarder_donnees(liste_actions):
    if liste_actions:
        pd.DataFrame(liste_actions).to_csv(FICHIER_DATA, index=False)
    elif os.path.exists(FICHIER_DATA):
        os.remove(FICHIER_DATA)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_donnees()

# --- 3. FONCTION GRAPHIQUE ---
def tracer_graphe(ticker, p, label):
    try:
        intervalle = "15m" if p == "1d" else "1h" if p == "5d" else "1d"
        data = yf.download(ticker, period=p, interval=intervalle, progress=False)
        if not data.empty:
            fig = go.Figure(data=[go.Scatter(x=data.index, y=data['Close'], line=dict(color='#00FF00', width=2))])
            fig.update_layout(
                title=f"{label} ({ticker})",
                height=300,
                template="plotly_dark",
                xaxis_rangeslider_visible=False,
                margin=dict(l=10, r=10, t=40, b=10)
            )
            st.plotly_chart(fig, use_container_width=True, key=f"plot_{ticker}_{p}")
    except:
        st.error(f"Erreur sur le graphe {label}")

# --- 4. NAVIGATION ---
tab_p, tab_g = st.tabs(["📊 Portefeuille", "📈 Graphes"])

# --- 5. CALCULS ---
if st.session_state.mon_portefeuille:
    total_actuel, total_achat, var_jour = 0, 0, 0
    donnees_pos = []

    for act in st.session_state.mon_portefeuille:
        try:
            t = yf.Ticker(act['Ticker'])
            h = t.history(period="2d")
            if not h.empty:
                p_act = h['Close'].iloc[-1]
                p_prev = h['Close'].iloc[-2] if len(h) > 1 else p_act
                
                v_act = p_act * act['Qté']
                total_actuel += v_act
                total_achat += (act['PRU'] * act['Qté'])
                var_jour += (p_act - p_prev) * act['Qté']
                
                donnees_pos.append({"act": act, "prix": p_act, "var": (p_act - p_prev) * act['Qté'], "val": v_act})
        except: pass

    # --- ONGLET PORTEFEUILLE ---
    with tab_p:
        pv_g = total_actuel - total_achat
        pv_p = (pv_g / total_achat * 100) if total_achat > 0 else 0
        vj_p = (var_jour / (total_actuel - var_jour) * 100) if (total_actuel - var_jour) > 0 else 0

        c1, c2, c3 = st.columns(3)
        c1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        c2.metric("P/L GLOBAL", f"{pv_g:.2f} €", delta=f"{pv_p:+.2f} %")
        c3.metric("VAR. JOUR", f"{var_jour:+.2f} €", delta=f"{vj_p:+.2f} %")
        st.divider()

        for i, item in enumerate(donnees_pos):
            a, p, v_l = item['act'], item['prix'], (item['prix'] - item['act']['PRU']) * item['act']['Qté']
            header = f"{'🟢' if v_l >= 0 else '🔴'} {a['Nom']} | {p:.2f}€ | {v_l:+.2f}€"
            with st.expander(header):
                st.write(f"**Quantité :** {a['Qté']} | **PRU :** {a['PRU']:.2f}€ | **Valeur :** {item['val']:.2f}€")
                st.write(f"**Variation Jour :** {item['var']:+.2f}€ | **Objectif :** {a.get('Seuil_Haut', 0)}€")
                if st.button("🗑️ Supprimer", key=f"del_{i}"):
                    st.session_state.mon_portefeuille.pop(i)
                    sauvegarder_donnees(st.session_state.mon_portefeuille)
                    st.rerun()

    # --- ONGLET GRAPHES ---
    with tab_g:
        choix = st.selectbox("Choisir une action :", [x['Nom'] for x in st.session_state.mon_portefeuille])
        t_sel = next(x['Ticker'] for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        
        per = [("1d", "Journée"), ("5d", "Semaine"), ("1mo", "Mois"), ("1y", "Année"), ("max", "Max")]
        for p, l in per:
            tracer_graphe(t_sel, p, l)

# --- 6. BARRE LATÉRALE (AJOUT & BACKUP) ---
with st.sidebar:
    st.header("🔍 Rechercher & Ajouter")
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
        f_p = st.number_input("PRU", min_value=0.0)
        f_q = st.number_input("Quantité", min_value=1)
        f_h = st.number_input("Objectif", min_value=0.0)
        if st.form_submit_button("Ajouter"):
            st.session_state.mon_portefeuille.append({"Nom": f_n, "Ticker": f_t.upper(), "PRU": f_n, "Qté": f_q, "Seuil_Haut": f_h})
            sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()

    st.divider()
    st.header("💾 Backup")
    df_b = pd.DataFrame(st.session_state.mon_portefeuille)
    st.download_button("📥 Télécharger", df_b.to_csv(index=False).encode('utf-8'), "data.csv")
    up = st.file_uploader("📤 Restaurer", type="csv")
    if up:
        st.session_state.mon_portefeuille = pd.read_csv(up).to_dict('records')
        sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()
