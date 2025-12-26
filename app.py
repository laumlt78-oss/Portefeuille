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
            val_ligne = item['val']
            pru = float(a['PRU'])
            qte = int(a['Qté'])
            
            # Calculs spécifiques
            pv_l = (p - pru) * qte
            pv_pente = ((p - pru) / pru * 100) if pru > 0 else 0
            poids = (val_ligne / total_actuel * 100) if total_actuel > 0 else 0
            obj = float(a.get('Seuil_Haut', 0.0))
            
            val_isin = str(a.get('ISIN', '')).strip()
            if val_isin.lower() in ["nan", "none"]: val_isin = ""
            
            header = f"{'🟢' if pv_l >= 0 else '🔴'} {a['Nom']} | {p:.2f}€ | {pv_l:+.2f}€ ({pv_pente:+.2f}%) | {val_isin}"
            
            with st.expander(header):
                edit_mode = st.toggle("📝 Modifier", key=f"edit_mode_{idx}")
                if edit_mode:
                    # ... (le formulaire reste le même que précédemment)
                    with st.form(f"form_edit_{idx}"):
                        col_e1, col_e2 = st.columns(2)
                        new_nom = col_e1.text_input("Nom", value=a['Nom'])
                        new_isin = col_e2.text_input("Code ISIN", value=val_isin)
                        new_pru = col_e1.number_input("PRU", value=pru, format="%.2f")
                        new_qte = col_e2.number_input("Quantité", value=qte, min_value=1)
                        new_obj = col_e1.number_input("Objectif", value=obj)
                        new_date = col_e2.date_input("Date achat", value=pd.to_datetime(a.get('Date_Achat', date.today())))
                        if st.form_submit_button("Enregistrer"):
                            st.session_state.mon_portefeuille[idx].update({
                                "Nom": new_nom, "ISIN": new_isin, "PRU": new_pru, 
                                "Qté": new_qte, "Seuil_Haut": new_obj, "Date_Achat": str(new_date)
                            })
                            sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()
                else:
                    # --- AFFICHAGE DES INFOS DÉTAILLÉES ---
                    col_info1, col_info2, col_info3 = st.columns(3)
                    
                    with col_info1:
                        st.write(f"**Quantité :** {qte}")
                        st.write(f"**PRU :** {pru:.2f} €")
                        st.write(f"**Poids Portefeuille :** {poids:.2f} %")
                    
                    with col_info2:
                        st.write(f"**Valeur Ligne :** {val_ligne:.2f} €")
                        st.write(f"**P/L Latent :** {pv_l:+.2f} € ({pv_pente:+.2f}%)")
                        st.write(f"**Date Achat :** {a.get('Date_Achat', 'N/C')}")
                    
                    with col_info3:
                        st.write(f"**Objectif :** {obj:.2f} €")
                        dist_obj = ((obj - p) / p * 100) if p > 0 and obj > 0 else 0
                        st.write(f"**Distance Obj :** {dist_obj:+.2f} %")
                        st.write(f"**ISIN :** {val_isin if val_isin else 'N/C'}")

                    if st.button("🗑️ Supprimer la ligne", key=f"del_btn_{idx}"):
                        st.session_state.mon_portefeuille.pop(idx)
                        sauvegarder_donnees(st.session_state.mon_portefeuille); st.rerun()
