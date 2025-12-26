import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests

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
        return pd.read_csv(FICHIER_DATA).to_dict('records')
    except: return []

def sauvegarder_donnees(liste_actions):
    if liste_actions:
        pd.DataFrame(liste_actions).to_csv(FICHIER_DATA, index=False)
    elif os.path.exists(FICHIER_DATA):
        os.remove(FICHIER_DATA)

if 'mon_portefeuille' not in st.session_state:
    st.session_state.mon_portefeuille = charger_donnees()

# --- 3. TITRE ET ZONE DE SAUVEGARDE ---
st.title("📈 Mon Portefeuille")

# Zone de boutons en haut à droite plus propre
col_t1, col_t2 = st.columns([3, 1])
with col_t2:
    # Bouton Export
    if st.session_state.mon_portefeuille:
        df_export = pd.DataFrame(st.session_state.mon_portefeuille)
        csv = df_export.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Sauvegarder (Backup)", data=csv, file_name='backup_portefeuille.csv', mime='text/csv', use_container_width=True)
    
    # Bouton Import avec gestion d'erreur corrigée
    uploaded_file = st.file_uploader("Restaurer un fichier", type="csv", label_visibility="collapsed")
    if uploaded_file:
        try:
            data_import = pd.read_csv(uploaded_file)
            if not data_import.empty:
                st.session_state.mon_portefeuille = data_import.to_dict('records')
                sauvegarder_donnees(st.session_state.mon_portefeuille)
                st.success("✅ Importé")
                st.rerun()
        except Exception:
            st.error("❌ Erreur de lecture")

st.divider()

# --- 4. RECHERCHE ET AJOUT (SIDEBAR) ---
with st.sidebar:
    st.header("🔍 Rechercher un titre")
    query = st.text_input("Nom ou ISIN", placeholder="Ex: LVMH ou FR0000121014")
    ticker_final, nom_final = "", ""
    if query:
        try:
            s = yf.Search(query, max_results=5)
            if s.quotes:
                options = {f"{q['shortname']} ({q['symbol']})": q['symbol'] for q in s.quotes}
                selection = st.selectbox("Résultats :", options.keys())
                ticker_final, nom_final = options[selection], selection.split(' (')[0]
        except: st.error("Recherche indisponible.")

    with st.form("ajout_form", clear_on_submit=True):
        f_nom = st.text_input("Nom", value=nom_final)
        f_ticker = st.text_input("Ticker", value=ticker_final)
        f_pru = st.number_input("PRU (Prix d'achat)", min_value=0.0, format="%.2f")
        f_qte = st.number_input("Quantité", min_value=1)
        f_haut = st.number_input("Seuil de vente (Haut)", min_value=0.0, format="%.2f")
        if st.form_submit_button("Ajouter au Portefeuille"):
            if f_ticker:
                st.session_state.mon_portefeuille.append({
                    "Nom": f_nom, "Ticker": f_ticker.upper(), "PRU": f_pru, "Qté": f_qte, "Seuil_Haut": f_haut
                })
                sauvegarder_donnees(st.session_state.mon_portefeuille)
                st.rerun()

# --- 5. CALCULS ET AFFICHAGE ---
if st.session_state.mon_portefeuille:
    total_actuel, total_achat = 0, 0
    donnees = []

    for act in st.session_state.mon_portefeuille:
        try:
            t = yf.Ticker(act['Ticker'])
            prix = t.fast_info['lastPrice']
            if prix is None or prix == 0:
                hist = t.history(period="1d")
                prix = hist['Close'].iloc[-1] if not hist.empty else 0
            
            val_act = prix * act['Qté']
            total_actuel += val_act
            total_achat += (act['PRU'] * act['Qté'])
            donnees.append({"act": act, "prix": prix, "val_act": val_act})
        except:
            donnees.append({"act": act, "prix": 0, "val_act": 0})

    # KPI Résumé
    pv_g_e = total_actuel - total_achat
    pv_g_p = (pv_g_e / total_achat * 100) if total_achat > 0 else 0
    c_m1, c_m2 = st.columns(2)
    c_m1.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
    c_m2.metric("P/L GLOBAL", f"{pv_g_e:.2f} €", delta=f"{pv_g_p:+.2f} %")
    st.divider()

    # Affichage des actions
    for i, item in enumerate(donnees):
        act, prix, val_act = item['act'], item['prix'], item['val_act']
        perf = ((prix / act['PRU']) - 1) * 100 if act['PRU'] > 0 else 0
        pv_e = (prix - act['PRU']) * act['Qté']
        
        color_circle = "🟢" if pv_e >= 0 else "🔴"
        signe = "+" if pv_e >= 0 else ""
        header = f"{color_circle} {act['Nom']} | {prix:.2f}€ | {perf:+.2f}% | {signe}{pv_e:.2f}€"
        
        with st.expander(header):
            color_style = "green" if pv_e >= 0 else "red"
            st.markdown(f"<h3 style='color:{color_style}; text-align:center;'>{signe}{pv_e:.2f} €</h3>", unsafe_allow_html=True)

            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.write("**Ma Position**")
                st.write(f"Quantité : {act['Qté']}")
                st.write(f"Valeur : {val_act:.2f}€")
            with c2:
                st.write("**Performances**")
                st.write(f"PRU : {act['PRU']:.2f}€")
                st.write(f"Part : {(val_act/total_actuel*100):.2f}%")
            with c3:
                st.write("**Seuils**")
                st.write(f"Bas (-20%) : {(act['PRU']*0.8):.2f}€")
                st.write(f"Haut : {act['Seuil_Haut']:.2f}€")
            with c4:
                st.write("**Action**")
                if st.button("🗑️ Supprimer", key=f"del_{i}"):
                    st.session_state.mon_portefeuille.pop(i)
                    sauvegarder_donnees(st.session_state.mon_portefeuille)
                    st.rerun()
else:
    st.info("👋 Portefeuille vide. Ajoutez un titre ou restaurez un backup.")
