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

st.title("📈 Assistant Portefeuille (Nom & ISIN)")

# --- 3. RECHERCHE ET AJOUT (SIDEBAR) ---
with st.sidebar:
    st.header("🔍 Rechercher un titre")
    query = st.text_input("Saisissez Nom ou ISIN", placeholder="Ex: LVMH ou FR0000121014")
    
    ticker_final = ""
    nom_final = ""
    
    if query:
        try:
            # On utilise yf.Search qui gère aussi bien les noms que les ISIN
            s = yf.Search(query, max_results=5)
            if s.quotes:
                options = {f"{q['shortname']} ({q['symbol']})": q['symbol'] for q in s.quotes}
                selection = st.selectbox("Titres trouvés :", options.keys())
                ticker_final = options[selection]
                nom_final = selection.split(' (')[0]
                st.success(f"Cible identifiée : {ticker_final}")
            else:
                st.warning("Aucun résultat. Essayez le Ticker directement.")
        except:
            st.error("Moteur de recherche indisponible. Saisissez les infos manuellement.")

    st.divider()
    st.header("📝 Détails de la ligne")
    with st.form("ajout_form", clear_on_submit=True):
        f_nom = st.text_input("Nom de l'action", value=nom_final)
        f_ticker = st.text_input("Ticker (Obligatoire)", value=ticker_final, help="Ex: MC.PA, TTE.PA, AAPL")
        f_isin = st.text_input("Code ISIN (Optionnel)", placeholder="FR000...")
        f_pru = st.number_input("Prix de revient (PRU)", min_value=0.0, format="%.2f")
        f_qte = st.number_input("Quantité", min_value=1)
        f_haut = st.number_input("Seuil de vente (Haut)", min_value=0.0, format="%.2f")
        
        if st.form_submit_button("Ajouter au Portefeuille"):
            if f_ticker:
                st.session_state.mon_portefeuille.append({
                    "Nom": f_nom, "Ticker": f_ticker.upper(), "ISIN": f_isin,
                    "PRU": f_pru, "Qté": f_qte, "Seuil_Haut": f_haut
                })
                sauvegarder_donnees(st.session_state.mon_portefeuille)
                st.rerun()
            else:
                st.error("Le Ticker est indispensable pour récupérer le prix.")

# --- 4. AFFICHAGE ET SUIVI ---
if st.session_state.mon_portefeuille:
    total_portefeuille = 0
    
    for i, act in enumerate(st.session_state.mon_portefeuille):
        try:
            t = yf.Ticker(act['Ticker'])
            # Récupération ultra-rapide du dernier prix
            prix = t.fast_info['lastPrice']
            
            valeur = prix * act['Qté']
            total_portefeuille += valeur
            perf = ((prix / act['PRU']) - 1) * 100 if act['PRU'] > 0 else 0
            s_bas = act['PRU'] * 0.80
            
            # Affichage en "cartes"
            with st.expander(f"**{act['Nom']}** | {prix:.2f}€ ({perf:+.2f}%)"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Valeur", f"{valeur:.2f}€")
                c1.write(f"Ticker: {act['Ticker']}")
                
                c2.write(f"PRU: {act['PRU']:.2f}€")
                c2.write(f"ISIN: {act.get('ISIN', 'N/A')}")
                
                if c3.button("🗑️ Supprimer", key=f"del_{i}"):
                    st.session_state.mon_portefeuille.pop(i)
                    sauvegarder_donnees(st.session_state.mon_portefeuille)
                    st.rerun()
                
                # Alertes
                if prix <= s_bas:
                    st.error(f"🚨 ALERTE BASSE : -20% atteint ({s_bas:.2f}€)")
                    envoyer_alerte(f"ALERTE : {act['Nom']} a chuté sous {s_bas:.2f}€")
                if act['Seuil_Haut'] > 0 and prix >= act['Seuil_Haut']:
                    st.success(f"💰 SEUIL HAUT : Objectif {act['Seuil_Haut']}€ atteint !")
                    envoyer_alerte(f"OBJECTIF : {act['Nom']} est à {prix:.2f}€")

        except Exception as e:
            st.error(f"Erreur sur {act['Ticker']}: Vérifiez que le ticker est correct (ex: MC.PA pour Paris).")

    st.divider()
    st.metric("VALEUR TOTALE", f"{total_portefeuille:.2f} €")
else:
    st.info("Utilisez la barre latérale pour rechercher et ajouter vos titres.")
