import streamlit as st
import yfinance as yf
import pandas as pd
import os
import requests
import base64
from datetime import date, datetime

# --- 1. VÉRIFICATION DES SECRETS ---
try:
    GH_TOKEN = st.secrets["GH_TOKEN"]
    GH_REPO = st.secrets["GH_REPO"]
    st.sidebar.success("✅ Secrets chargés")
except Exception as e:
    st.error(f"❌ Erreur de Secrets : {e}")
    st.stop()

st.set_page_config(page_title="Diagnostic Portefeuille", layout="wide")

# --- 2. FONCTION DE SAUVEGARDE AVEC DEBUG ---
def sauvegarder_vers_github_debug(liste):
    url = f"https://api.github.com/repos/{GH_REPO}/contents/portefeuille_data.csv"
    headers = {"Authorization": f"token {GH_TOKEN}"}
    
    # Transformation en CSV
    df = pd.DataFrame(liste)
    csv_content = df.to_csv(index=False)
    
    # Étape 1 : Vérifier si le fichier existe déjà
    r_get = requests.get(url, headers=headers)
    sha = r_get.json().get('sha') if r_get.status_code == 200 else None
    
    # Étape 2 : Envoyer les données
    payload = {
        "message": "Update portefeuille",
        "content": base64.b64encode(csv_content.encode('utf-8')).decode('utf-8')
    }
    if sha: payload["sha"] = sha
    
    r_put = requests.put(url, headers=headers, json=payload)
    
    if r_put.status_code in [200, 201]:
        st.success("🎉 Bravo ! Le fichier a été créé/mis à jour sur GitHub.")
        return True
    else:
        st.error(f"❌ Échec GitHub. Code : {r_put.status_code}")
        st.json(r_put.json()) # Affiche l'erreur exacte de GitHub
        return False

# --- 3. INTERFACE DE RÉPARATION ---
st.header("🛠️ Réparation de la base de données")

col1, col2 = st.columns(2)

with col1:
    st.subheader("1. Restaurer depuis votre PC")
    up = st.file_uploader("Envoyez votre dernier fichier CSV", type="csv")
    if up:
        df_restored = pd.read_csv(up)
        # Nettoyage minimal
        if 'Ticker' in df_restored.columns:
            st.write("Fichier valide détecté.")
            if st.button("🚀 Envoyer ces données vers GitHub"):
                success = sauvegarder_vers_github_debug(df_restored.to_dict('records'))
                if success: st.info("Rafraîchissez la page maintenant.")
        else:
            st.error("Le fichier CSV doit au moins contenir une colonne 'Ticker'.")

with col2:
    st.subheader("2. Test de connexion")
    if st.button("📝 Créer un fichier de test vide sur GitHub"):
        test_data = [{"Nom": "Test", "Ticker": "OR.PA", "PRU": 100, "Qté": 1, "Date_Achat": str(date.today())}]
        sauvegarder_vers_github_debug(test_data)

st.divider()
st.info("💡 Une fois que le bouton 'Envoyer vers GitHub' affiche un message vert, vos données seront sauvées à vie.")
