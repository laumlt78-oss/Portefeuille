import yfinance as yf
import pandas as pd
import requests
import os
import sys
from datetime import datetime, timedelta

# --- CONFIGURATION ---
USER_KEY = os.getenv("PUSHOVER_USER_KEY")
API_TOKEN = os.getenv("PUSHOVER_API_TOKEN")
GH_REPO = os.getenv("GH_REPO")
MODE = sys.argv[1] if len(sys.argv) > 1 else "check"

def send_push(title, message):
    payload = {"token": API_TOKEN, "user": USER_KEY, "title": title, "message": message}
    requests.post("https://api.pushover.net/1/messages.json", data=payload)

def load_github_csv(filename):
    url = f"https://raw.githubusercontent.com/{GH_REPO}/main/{filename}"
    try:
        df = pd.read_csv(url)
        return df
    except:
        return pd.DataFrame()

# --- 1. CHARGEMENT DES DONNÉES ---
df_p = load_github_csv("portefeuille_data.csv")
df_w = load_github_csv("watchlist_data.csv")
df_d = load_github_csv("dividendes_data.csv")

# --- 2. RÉVEIL STREAMLIT ---
try:
    url_app = "https://portefeuille-xppf99tytxydkyaljnmncu.streamlit.app/"
    headers = {"User-Agent": "Mozilla/5.0"}
    requests.get(url_app, headers=headers, timeout=15)
except: pass

# --- 3. TRAITEMENT ---
total_achat = 0
total_actuel = 0
total_veille = 0
flash_news = ""
watchlist_alerts = ""

# A. Analyse Portefeuille
if not df_p.empty:
    for _, row in df_p.iterrows():
        try:
            tk = yf.Ticker(row['Ticker'])
            hist = tk.history(period="2d")
            price = hist['Close'].iloc[-1]
            price_h = hist['Close'].iloc[-2] if len(hist) > 1 else price
            
            qte = float(row['Qté'])
            total_achat += (float(row['PRU']) * qte)
            total_actuel += (price * qte)
            total_veille += (price_h * qte)

            # Alertes Portefeuille (Mode Check)
            if MODE == "check":
                if price <= float(row['Seuil_Bas']):
                    send_push("⚠️ ALERTE BASSE", f"{row['Nom']} : {price:.2f}€ (Seuil: {row['Seuil_Bas']}€)")
                elif float(row.get('Seuil_Haut', 0)) > 0 and price >= float(row['Seuil_Haut']):
                    send_push("🚀 OBJECTIF ATTEINT", f"{row['Nom']} : {price:.2f}€ (Objectif: {row['Seuil_Haut']}€)")

            # News (24h)
            news = tk.news
            if news and (datetime.fromtimestamp(news[0]['providerPublishTime']) > datetime.now() - timedelta(hours=24)):
                flash_news += f"🗞️ {row['Nom']} : {news[0]['title']}\n"
        except: continue

# B. Analyse Watchlist (Mode Check uniquement)
if MODE == "check" and not df_w.empty:
    for _, row in df_w.iterrows():
        try:
            tk = yf.Ticker(row['Ticker'])
            p_w = tk.fast_info.last_price
            if p_w <= float(row['Seuil_Alerte']):
                watchlist_alerts += f"🎯 {row['Nom']} a touché son seuil : {p_w:.2f}€\n"
        except: continue

# C. Calcul Dividendes
total_div = df_d['Montant'].sum() if not df_d.empty else 0

# --- 4. ENVOI DES NOTIFICATIONS ---

# Calculs sans dividendes (Bourse uniquement)
pv_euros_bourse = total_actuel - total_achat
perf_pct_bourse = (pv_euros_bourse / total_achat * 100) if total_achat > 0 else 0

# Calculs avec dividendes (Richesse totale)
richesse_totale = total_actuel + total_div
pv_euros_totale = richesse_totale - total_achat
perf_pct_totale = (pv_euros_totale / total_achat * 100) if total_achat > 0 else 0

# Variation du jour (santé du marché)
perf_jour = ((total_actuel - total_veille) / total_veille * 100) if total_veille > 0 else 0

if MODE == "open":
    send_push("🔔 OUVERTURE", f"Valeur : {total_actuel:.2f}€\nPerf Portefeuille : {perf_pct_bourse:+.2f}%")

elif MODE == "close":
    msg = (
        f"🏁 CLÔTURE\n"
        f"---------------------------\n"
        f"📊 BILAN BOURSIER (Actions)\n"
        f"Valeur : {total_actuel:.2f}€\n"
        f"Var. Jour : {perf_jour:+.2f}%\n"
        f"+/- Value : {pv_euros_bourse:+.2f}€ ({perf_pct_bourse:+.2f}%)\n"
        f"---------------------------\n"
        f"💰 RICHESSE TOTALE (+Div)\n"
        f"Total : {richesse_totale:.2f}€\n"
        f"Dividendes perçus : {total_div:.2f}€\n"
        f"Performance Réelle : {pv_euros_totale:+.2f}€ ({perf_pct_totale:+.2f}%)\n"
        f"---------------------------\n"
        f"📰 RECAP NEWS :\n{flash_news if flash_news else 'Aucune.'}"
    )
    send_push("🏁 BILAN DU JOUR", msg)

elif MODE == "check":
    # Alertes Watchlist
    if watchlist_alerts:
        send_push("🔍 OPPORTUNITÉ WATCHLIST", watchlist_alerts)
    # News flash
    if flash_news and "GITHUB_ACTIONS" in os.environ and os.getenv("GITHUB_EVENT_NAME") == "workflow_dispatch":
        send_push("🗞️ FLASH INFO", flash_news)
