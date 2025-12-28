import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import base64
import plotly.graph_objects as go
from datetime import date, datetime

# --- 1. CONFIGURATION SECRETS ---
try:
    USER_KEY = st.secrets["PUSHOVER_USER_KEY"]
    API_TOKEN = st.secrets["API_TOKEN"] # Assurez-vous du nom exact dans vos secrets
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
except Exception as e:
    st.error(f"Secrets manquants : {e}")
    st.stop()

st.set_page_config(page_title="Mon Portefeuille Pro", layout="wide")

# --- 2. FONCTIONS GITHUB ---
FICHIER_DATA = "portefeuille_data.csv"
HEADERS_GH = {"Authorization": f"token {GH_TOKEN}"}

def charger_depuis_github():
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{FICHIER_DATA}"
    try:
        r = requests.get(url, headers=HEADERS_GH, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            from io import StringIO
            df = pd.read_csv(StringIO(content))
            return df.to_dict('records')
    except: pass
    return []

def sauvegarder_vers_github(liste):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{FICHIER_DATA}"
    df = pd.DataFrame(liste)
    csv_content = df.to_csv(index=False)
    
    r_get = requests.get(url, headers=HEADERS_GH, timeout=10)
    sha = r_get.json().get('sha') if r_get.status_code == 200 else None
    
    payload = {
        "message": f"Sync {datetime.now().strftime('%d/%m %H:%M')}",
        "content": base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
    }
    if sha: payload["sha"] = sha
    requests.put(url, headers=HEADERS_GH, json=payload, timeout=10)

# Initialisation
if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_depuis_github()

# --- 3. FONCTIONS GRAPHIQUES ---
def tracer_graphe(ticker, date_achat, nom):
    try:
        # On télécharge depuis la date d'achat
        df_h = yf.download(ticker, start=date_achat, progress=False)
        if not df_h.empty:
            fig = go.Figure(go.Scatter(x=df_h.index, y=df_h['Close'], line=dict(color='#00FF00', width=2)))
            fig.update_layout(
                title=f"Évolution de {nom} depuis l'achat ({date_achat})",
                template="plotly_dark",
                xaxis=dict(tickformat="%d %b %y", showgrid=False),
                yaxis=dict(side="right", title="Prix (€)"),
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"Aucune donnée boursière trouvée pour {ticker}")
    except:
        st.error("Erreur lors du chargement du graphique.")

# --- 4. CALCULS ET AFFICHAGE ---
tab_p, tab_g = st.tabs(["📊 Portefeuille", "📈 Graphiques"])

total_actuel, total_achat, var_jour = 0.0, 0.0, 0.0
donnees_pos = []

# Récupération des cours en direct
if st.session_state.mon_portefeuille:
    for i, act in enumerate(st.session_state.mon_portefeuille):
        try:
            t = yf.Ticker(act['Ticker'])
            h = t.history(period="2d")
            if not h.empty:
                p_act = h['Close'].iloc[-1]
                p_prev = h['Close'].iloc[-2] if len(h) > 1 else p_act
                qte = float(act['Qté'])
                pru = float(act['PRU'])
                
                val_l = p_act * qte
                total_actuel += val_l
                total_achat += (pru * qte)
                var_jour += (p_act - p_prev) * qte
                donnees_pos.append({"idx": i, "act": act, "prix": p_act, "val": val_l})
        except:
            st.sidebar.error(f"Erreur sur le ticker : {act['Ticker']}")

with tab_p:
    if total_achat > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
        pl_g = total_actuel - total_achat
        c2.metric("P/L GLOBAL", f"{pl_g:.2f} €", delta=f"{(pl_g/total_achat*100):+.2f} %")
        c3.metric("VAR. JOUR", f"{var_jour:+.2f} €")
        st.divider()

    for item in donnees_pos:
        idx, a, p = item['idx'], item['act'], item['prix']
        pru, qte = float(a['PRU']), float(a['Qté'])
        pv_l = (p - pru) * qte
        pv_p = (pv_l / (pru * qte) * 100) if pru > 0 else 0
        poids = (item['val'] / total_actuel * 100) if total_actuel > 0 else 0
        
        header = f"{'🟢' if pv_l >= 0 else '🔴'} {a['Nom']} | {p:.2f}€ | {pv_l:+.2f}€ ({pv_p:+.2f}%)"
        with st.expander(header):
            col1, col2, col3 = st.columns(3)
            col1.write(f"**Quantité :** {qte}")
            col1.write(f"**PRU :** {pru:.2f} €")
            col2.write(f"**Poids :** {poids:.2f} %")
            col2.write(f"**Valeur :** {item['val']:.2f} €")
            col3.write(f"**ISIN :** {a.get('ISIN', 'N/A')}")
            col3.write(f"**Achat :** {a.get('Date_Achat', 'N/A')}")
            
            if st.button("🗑️ Supprimer", key=f"del_{idx}"):
                st.session_state.mon_portefeuille.pop(idx)
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()

with tab_g:
    if st.session_state.mon_portefeuille:
        choix = st.selectbox("Action à analyser :", [x['Nom'] for x in st.session_state.mon_portefeuille])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        tracer_graphe(info['Ticker'], info['Date_Achat'], info['Nom'])
    else:
        st.info("Ajoutez des actions pour voir les graphiques.")

# --- 5. SIDEBAR : AJOUT ---
with st.sidebar:
    st.header("🔍 Ajouter un Titre")
    with st.form("add_form", clear_on_submit=True):
        f_n = st.text_input("Nom")
        f_i = st.text_input("ISIN")
        f_t = st.text_input("Ticker (ex: AI.PA, AAPL)")
        f_p = st.number_input("PRU", min_value=0.0, format="%.2f")
        f_q = st.number_input("Quantité", min_value=0.0, format="%.2f")
        f_d = st.date_input("Date d'achat", value=date.today())
        if st.form_submit_button("Ajouter au Portefeuille"):
            if f_n and f_t:
                nouvelle_ligne = {
                    "Nom": f_n, "ISIN": f_i, "Ticker": f_t.upper(),
                    "PRU": f_p, "Qté": f_q, "Date_Achat": str(f_d)
                }
                st.session_state.mon_portefeuille.append(nouvelle_ligne)
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.success("Synchronisé sur GitHub !")
                st.rerun()
            else:
                st.error("Nom et Ticker obligatoires.")

    st.divider()
    dt_str = datetime.now().strftime("%Y%m%d_%H%M")
    df_dl = pd.DataFrame(st.session_state.mon_portefeuille)
    st.download_button(f"📥 Backup PC ({dt_str})", df_dl.to_csv(index=False), f"portefeuille_{dt_str}.csv")
