import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import base64
import plotly.graph_objects as go
from datetime import date, datetime, timedelta

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Portefeuille Expert", layout="wide", initial_sidebar_state="expanded")

try:
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
except:
    st.error("Secrets GitHub manquants.")
    st.stop()

# --- 2. GESTION GITHUB ---
FICHIER_DATA = "portefeuille_data.csv"
HEADERS_GH = {"Authorization": f"token {GH_TOKEN}"}

def charger_depuis_github():
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{FICHIER_DATA}"
    try:
        r = requests.get(url, headers=HEADERS_GH, timeout=10)
        if r.status_code == 200:
            content = base64.b64decode(r.json()['content']).decode('utf-8')
            from io import StringIO
            return pd.read_csv(StringIO(content)).to_dict('records')
    except: pass
    return []

def sauvegarder_vers_github(liste):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/{FICHIER_DATA}"
    df = pd.DataFrame(liste)
    csv_content = df.to_csv(index=False)
    r_get = requests.get(url, headers=HEADERS_GH, timeout=10)
    sha = r_get.json().get('sha') if r_get.status_code == 200 else None
    payload = {"message": "Sync", "content": base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')}
    if sha: payload["sha"] = sha
    requests.put(url, headers=HEADERS_GH, json=payload, timeout=10)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_depuis_github()

# --- 3. MOTEUR DE GRAPHIQUES ---
def tracer_courbe(df, titre, pru=None, s_h=None, s_b=None):
    if df is None or df.empty:
        st.warning("Pas de données.")
        return
    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color='#00FF00', width=2)))
    if pru: fig.add_hline(y=float(pru), line_dash="dash", line_color="orange", annotation_text="PRU")
    if s_h and float(s_h) > 0: fig.add_hline(y=float(s_h), line_color="green", line_width=1.5, annotation_text="Vente")
    if s_b and float(s_b) > 0: fig.add_hline(y=float(s_b), line_color="red", line_width=1.5, annotation_text="Stop")
    fig.update_layout(template="plotly_dark", hovermode="x unified", height=500, xaxis=dict(tickformat="%d/%m/%y"))
    st.plotly_chart(fig, use_container_width=True)

# --- 4. BARRE LATÉRALE ---
with st.sidebar:
    st.header("⚙️ Gestion")
    with st.form("add_form", clear_on_submit=True):
        st.subheader("➕ Ajouter")
        n, i, t = st.text_input("Nom"), st.text_input("ISIN"), st.text_input("Ticker")
        p, q = st.number_input("PRU", min_value=0.0), st.number_input("Qté", min_value=0.0)
        d = st.date_input("Achat", value=date.today())
        sh = st.number_input("Seuil Haut", min_value=0.0)
        sb = st.number_input("Seuil Bas (0=Auto)", min_value=0.0)
        if st.form_submit_button("Ajouter"):
            if n and t:
                v_sb = sb if sb > 0 else (p * 0.7)
                st.session_state.mon_portefeuille.append({"Nom":n,"ISIN":i,"Ticker":t.upper(),"PRU":p,"Qté":q,"Date_Achat":str(d),"Seuil_Haut":sh,"Seuil_Bas":v_sb})
                sauvegarder_vers_github(st.session_state.mon_portefeuille)
                st.rerun()

# --- 5. CALCULS ET ONGLETS ---
tab1, tab2 = st.tabs(["📊 Portefeuille", "📈 Graphiques"])

with tab1:
    total_val, total_ach = 0.0, 0.0
    
    for idx, act in enumerate(st.session_state.mon_portefeuille):
        # 1. Calculs financiers
        try:
            tk = yf.Ticker(act['Ticker'])
            hist = tk.history(period="1d")
            c_act = hist['Close'].iloc[-1] if not hist.empty else 0
        except:
            c_act = 0
            
        pru = float(act['PRU'])
        qte = float(act['Qté'])
        s_b = float(act.get('Seuil_Bas', 0))
        if s_b == 0: s_b = pru * 0.7
        
        val_titre = c_act * qte
        pv_euro = val_titre - (pru * qte)
        pv_perc = (pv_euro / (pru * qte) * 100) if (pru * qte) > 0 else 0
        
        total_val += val_titre
        total_ach += (pru * qte)

        # 2. Détermination de l'icône
        if c_act > 0 and c_act < s_b:
            icone = "⚠️"
        elif pv_euro >= 0:
            icone = "🟢"
        else:
            icone = "🔴"

        # 3. Construction du titre (TRÈS PRÉCIS)
        titre_complet = f"{icone} {act['Nom']} | Cours: {c_act:.2f}€ | P/L: {pv_euro:+.2f}€ ({pv_perc:+.2f}%)"

        # 4. Affichage
        with st.expander(titre_complet):
            col1, col2, col3, col4 = st.columns([2,2,2,1])
            with col1:
                st.write(f"**ISIN:** {act.get('ISIN')}")
                st.write(f"**PRU:** {pru:.2f}€")
            with col2:
                st.write(f"**Quantité:** {qte}")
                st.write(f"**Valeur Totale:** {val_titre:.2f}€")
            with col3:
                st.write(f"**Seuil Haut:** {act.get('Seuil_Haut', 0):.2f}€")
                st.write(f"**Seuil Bas:** {s_b:.2f}€")
            with col4:
                if st.button("✏️", key=f"edit_{idx}"): st.session_state[f"mode_{idx}"] = True
                if st.button("🗑️", key=f"del_{idx}"):
                    st.session_state.mon_portefeuille.pop(idx)
                    sauvegarder_vers_github(st.session_state.mon_portefeuille)
                    st.rerun()
            
            # Formulaire de modification
            if st.session_state.get(f"mode_{idx}", False):
                with st.form(f"form_{idx}"):
                    n_pru = st.number_input("Nouveau PRU", value=pru)
                    n_qte = st.number_input("Nouvelle Quantité", value=qte)
                    n_sh = st.number_input("Nouveau Seuil Haut", value=float(act.get('Seuil_Haut', 0)))
                    n_sb = st.number_input("Nouveau Seuil Bas", value=s_b)
                    if st.form_submit_button("Enregistrer"):
                        st.session_state.mon_portefeuille[idx].update({"PRU":n_pru,"Qté":n_qte,"Seuil_Haut":n_sh,"Seuil_Bas":n_sb})
                        sauvegarder_vers_github(st.session_state.mon_portefeuille)
                        del st.session_state[f"mode_{idx}"]
                        st.rerun()

    # Affichage du résumé global en haut
    if total_ach > 0:
        st.sidebar.divider()
        st.sidebar.metric("VALEUR TOTALE", f"{total_val:.2f} €")
        diff = total_val - total_ach
        perc = (diff / total_ach) * 100
        st.sidebar.metric("P/L GLOBAL", f"{diff:+.2f} €", delta=f"{perc:+.2f} %")

with tab2:
    if st.session_state.mon_portefeuille:
        sel = st.selectbox("Choisir l'action", [x['Nom'] for x in st.session_state.mon_portefeuille])
        info = next(x for x in st.session_state.mon_portefeuille if x['Nom'] == sel)
        df_h = yf.download(info['Ticker'], start=info['Date_Achat'], progress=False)
        tracer_courbe(df_h, info['Nom'], pru=info['PRU'], s_h=info.get('Seuil_Haut'), s_b=info.get('Seuil_Bas'))
