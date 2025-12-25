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

st.title("📈 Suivi de Portefeuille")

# --- 3. RECHERCHE ET AJOUT (SIDEBAR) ---
with st.sidebar:
    st.header("🔍 Rechercher un titre")
    query = st.text_input("Saisissez Nom ou ISIN", placeholder="Ex: LVMH ou FR0000121014")
    
    ticker_final, nom_final = "", ""
    if query:
        try:
            s = yf.Search(query, max_results=5)
            if s.quotes:
                options = {f"{q['shortname']} ({q['symbol']})": q['symbol'] for q in s.quotes}
                selection = st.selectbox("Titres trouvés :", options.keys())
                ticker_final = options[selection]
                nom_final = selection.split(' (')[0]
        except:
            st.error("Moteur de recherche indisponible.")

    st.divider()
    with st.form("ajout_form", clear_on_submit=True):
        f_nom = st.text_input("Nom de l'action", value=nom_final)
        f_ticker = st.text_input("Ticker (Obligatoire)", value=ticker_final)
        f_pru = st.number_input("Prix de revient (PRU)", min_value=0.0, format="%.2f")
        f_qte = st.number_input("Quantité", min_value=1)
        f_haut = st.number_input("Seuil de vente (Haut)", min_value=0.0, format="%.2f")
        if st.form_submit_button("Ajouter"):
            if f_ticker:
                st.session_state.mon_portefeuille.append({
                    "Nom": f_nom, "Ticker": f_ticker.upper(), "PRU": f_pru, "Qté": f_qte, "Seuil_Haut": f_haut
                })
                sauvegarder_donnees(st.session_state.mon_portefeuille)
                st.rerun()

# --- 4. CALCULS GLOBAUX ---
if st.session_state.mon_portefeuille:
    donnees_affichees = []
    total_actuel = 0
    total_achat_initial = 0

    for act in st.session_state.mon_portefeuille:
        try:
            t = yf.Ticker(act['Ticker'])
            prix = t.fast_info['lastPrice']
            valeur_actuelle = prix * act['Qté']
            valeur_achat = act['PRU'] * act['Qté']
            
            total_actuel += valeur_actuelle
            total_achat_initial += valeur_achat
            
            donnees_affichees.append({"act": act, "prix": prix, "valeur": valeur_actuelle})
        except:
            donnees_affichees.append({"act": act, "prix": 0, "valeur": 0})

    # --- AFFICHAGE DU RÉSUMÉ (KPI) ---
    pv_globale_euros = total_actuel - total_achat_initial
    pv_globale_pct = (pv_globale_euros / total_achat_initial * 100) if total_achat_initial > 0 else 0

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("VALEUR TOTALE", f"{total_actuel:.2f} €")
    with col_m2:
        # Le paramètre 'delta' gère automatiquement le vert/rouge
        st.metric(
            "PLUS/MOINS-VALUE TOTALE", 
            f"{pv_globale_euros:.2f} €", 
            delta=f"{pv_globale_pct:+.2f} %"
        )
    
    st.divider()

    # --- 5. AFFICHAGE DES CARTES INDIVIDUELLES ---
    for i, item in enumerate(donnees_affichees):
        act = item['act']
        prix = item['prix']
        valeur = item['valeur']
        
        if prix > 0:
            perf_pct = ((prix / act['PRU']) - 1) * 100 if act['PRU'] > 0 else 0
            plus_value_euros = (prix - act['PRU']) * act['Qté']
            seuil_bas = act['PRU'] * 0.80
            part_pourtentage = (valeur / total_actuel) * 100 if total_actuel > 0 else 0
            
            signe = "+" if plus_value_euros >= 0 else ""
            header_text = f"**{act['Nom']}** | {prix:.2f}€ | {perf_pct:+.2f}% | {signe}{plus_value_euros:.2f}€"
            
            with st.expander(header_text):
                if plus_value_euros >= 0:
                    st.success(f"Gain latent : {plus_value_euros:.2f} €")
                else:
                    st.error(f"Perte latente : {abs(plus_value_euros):.2f} €")

                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.write("**Ma Position**")
                    st.write(f"Quantité : {act['Qté']}")
                    st.write(f"Valeur : {valeur:.2f}€")
                with c2:
                    st.write("**Performances**")
                    st.write(f"PRU : {act['PRU']:.2f}€")
                    st.write(f"Part : **{part_pourtentage:.2f}%**")
                with c3:
                    st.write("**Seuils d'Alerte**")
                    st.write(f"Bas (-20%) : {seuil_bas:.2f}€")
                    st.write(f"Haut (Vente) : {act['Seuil_Haut']:.2f}€")
                with c4:
                    st.write("**Action**")
                    if st.button("🗑️ Supprimer", key=f"del_{i}"):
                        st.session_state.mon_portefeuille.pop(i)
                        sauvegarder_donnees(st.session_state.mon_portefeuille)
                        st.rerun()

                # Alertes Pushover
                if prix <= seuil_bas:
                    envoyer_alerte(f"🚨 ALERTE : {act['Nom']} chute ({prix:.2f}€)")
                if act['Seuil_Haut'] > 0 and prix >= act['Seuil_Haut']:
                    envoyer_alerte(f"🎯 OBJECTIF : {act['Nom']} atteint ({prix:.2f}€)")
        else:
            st.error(f"Données indisponibles pour {act['Ticker']}")
else:
    st.info("Utilisez la barre latérale pour ajouter vos titres.")
