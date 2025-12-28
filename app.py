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
    # On essaie de récupérer la clé, peu importe son nom
    API_TOKEN = st.secrets.get("API_TOKEN") or st.secrets.get("PUSHOVER_API_TOKEN")
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
    
    if not API_TOKEN:
        st.error("La clé API_TOKEN est manquante dans les Secrets Streamlit.")
        st.stop()
except Exception as e:
    st.error(f"Erreur de configuration des Secrets : {e}")
    st.stop()

# --- 2. GESTION GITHUB ---
FICHIER_DATA = "portefeuille_data.csv"
COLS_VALIDEES = ['Nom', 'ISIN', 'Ticker', 'PRU', 'Qté', 'Date_Achat']
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
        "message": f"Auto-sync {datetime.now().strftime('%d/%m %H:%M')}",
        "content": base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
    }
    if sha: payload["sha"] = sha
    requests.put(url, headers=HEADERS_GH, json=payload, timeout=10)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_depuis_github()

# --- 3. GRAPHISMES ---
def tracer_graphe(ticker, date_achat_str, nom):
    try:
        # 1. Calcul de la date de début pour avoir du contexte
        d_achat = datetime.strptime(date_achat_str, '%Y-%m-%d').date()
        # On remonte 30 jours avant l'achat pour voir la tendance d'arrivée
        d_debut_vue = d_achat - pd.Timedelta(days=30)
        
        # 2. Téléchargement des données
        df_h = yf.download(ticker, start=d_debut_vue, progress=False)
        
        if not df_h.empty:
            fig = go.Figure()

            # Courbe des cours
            fig.add_trace(go.Scatter(
                x=df_h.index, 
                y=df_h['Close'], 
                line=dict(color='#00FF00', width=2),
                name="Cours",
                hovertemplate="Date: %{x}<br>Prix: %{y:.2f} €" # Format 2 décimales
            ))

            # Ligne horizontale du PRU (Prix d'achat)
            pru_val = float(next(x['PRU'] for x in st.session_state.mon_portefeuille if x['Nom'] == nom))
            fig.add_hline(
                y=pru_val, 
                line_dash="dash", 
                line_color="orange", 
                annotation_text=f"Mon PRU: {pru_val:.2f}€",
                annotation_position="top left"
            )

            # Ligne verticale Date d'achat
            fig.add_vline(x=d_achat, line_width=1, line_dash="dot", line_color="white")

            fig.update_layout(
                title=f"Historique {nom} (Achat le {d_achat.strftime('%d/%m/%Y')})",
                template="plotly_dark",
                xaxis=dict(
                    tickformat="%d %b %y",
                    rangeslider=dict(visible=False), # Désactive le slider pour gagner de la place
                    showgrid=False
                ),
                yaxis=dict(
                    side="right", 
                    title="Prix (€)",
                    tickformat=".2f" # Force 2 chiffres après la virgule sur l'axe
                ),
                height=450,
                margin=dict(l=20, r=20, t=60, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning(f"Impossible de récupérer l'historique pour {ticker}. Vérifiez le symbole sur Yahoo Finance.")
    except Exception as e:
        st.error(f"Erreur lors du tracé : {e}")

# --- 4. CALCULS ET ONGLETS ---
tab_p, tab_g = st.tabs(["📊 Mon Portefeuille", "📈 Graphiques Historiques"])

total_actuel, total_achat, var_jour = 0.0, 0.0, 0.0
donnees_pos = []

if st.session_state.mon_portefeuille:
    for i, act in enumerate(st.session_state.mon_portefeuille):
        try:
            t = yf.Ticker(act['Ticker'])
            h = t.history(period="2d")
            if not h.empty:
                p_act = h['Close'].iloc[-1]
                p_prev = h['Close'].iloc[-2] if len(h) > 1 else p_act
                qte, pru = float(act['Qté']), float(act['PRU'])
                val_l = p_act * qte
                total_actuel += val_l
                total_achat += (pru * qte)
                var_jour += (p_act - p_prev) * qte
                donnees_pos.append({"idx": i, "act": act, "prix": p_act, "val": val_l})
        except: pass

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
            col3.write(f"**Date Achat :** {a.get('Date_Achat', 'N/A')}")
            if st.button("🗑️ Supprimer", key=f"del_{idx}"):
                st.session_state.mon_portefeuille.pop(idx)
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()

with tab_g:
    if st.session_state.mon_portefeuille:
        choix = st.selectbox("Choisir une action :", [x['Nom'] for x in st.session_state.mon_portefeuille])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == choix)
        tracer_graphe(info['Ticker'], info['Date_Achat'], info['Nom'])


# --- 5. SIDEBAR (AJOUT ET RESTAURATION) ---
with st.sidebar:
    st.header("🔍 Gestion")
    with st.form("add_form", clear_on_submit=True):
        f_n = st.text_input("Nom")
        f_i = st.text_input("ISIN")
        f_t = st.text_input("Ticker (ex: AI.PA)")
        f_p = st.number_input("PRU", min_value=0.0, format="%.2f")
        f_q = st.number_input("Quantité", min_value=0.0, format="%.2f")
        f_d = st.date_input("Date d'achat", value=date.today())
        if st.form_submit_button("Ajouter"):
            if f_n and f_t:
                st.session_state.mon_portefeuille.append({
                    "Nom": f_n, "ISIN": f_i, "Ticker": f_t.upper(),
                    "PRU": f_p, "Qté": f_q, "Date_Achat": str(f_d)
                })
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()

    st.divider()
    st.subheader("⚙️ Maintenance")
    
    # --- BLOC RESTAURATION CORRIGÉ ---
    up = st.file_uploader("📤 Restaurer depuis PC", type="csv")
    if up:
        try:
            df_up = pd.read_csv(up)
            # Vérifie et ajoute les colonnes manquantes
            for col in COLS_VALIDEES:
                if col not in df_up.columns:
                    # Correction : on définit une valeur par défaut selon la colonne
                    if col in ['ISIN', 'Nom', 'Ticker']:
                        df_up[col] = ""
                    elif col == 'Date_Achat':
                        df_up[col] = str(date.today())
                    else:
                        df_up[col] = 0.0
            
            st.session_state.mon_portefeuille = df_up.to_dict('records')
            sauvegarder_vers_github(st.session_state.mon_portefeuille)
            st.success("✅ Données synchronisées sur GitHub !")
            st.rerun()
        except Exception as e:
            st.error(f"Fichier invalide : {e}")
    
    # Backup
    dt_s = datetime.now().strftime("%Y%m%d_%H%M")
    df_dl = pd.DataFrame(st.session_state.mon_portefeuille)
    st.download_button(f"📥 Backup PC ({dt_s})", df_dl.to_csv(index=False), f"portefeuille_{dt_s}.csv")




