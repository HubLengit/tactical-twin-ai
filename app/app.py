import streamlit as st
import requests
import time
import os

API_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="TacticalTwin AI", page_icon="⚽", layout="wide")

st.title("⚽ TacticalTwin AI - Le Coach Virtuel")
st.markdown("Plateforme d'analyse tactique automatisée propulsée par Computer Vision et LLM local.")

st.sidebar.header("Configuration")
uploaded_file = st.sidebar.file_uploader("Uploader une séquence (MP4)", type=["mp4"])

if uploaded_file is not None:
    # 1. Sauvegarde temporaire de la vidéo pour l'API
    video_path = os.path.join("data", "raw", uploaded_file.name)
    with open(video_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    st.sidebar.success(f"Vidéo chargée : {uploaded_file.name}")
    
    if st.sidebar.button("🚀 Lancer l'Analyse Tactique"):
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("📡 Statut du Système Distribué")
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            # 2. Requête à FastAPI pour déclencher le Worker (Celery)
            status_text.info("Envoi de la vidéo au cluster de traitement...")
            response = requests.post(f"{API_URL}/analyze/?video_path={video_path}")
            
            if response.status_code == 200:
                task_id = response.json()["task_id"]
                status_text.warning("Tâche en cours sur le GPU (MPS)... Veuillez patienter.")
                
                # 3. Boucle de Polling (Vérification du statut toutes les 2 secondes)
                task_status = "PENDING"
                while task_status not in ["SUCCESS", "FAILURE"]:
                    time.sleep(2)
                    status_response = requests.get(f"{API_URL}/status/{task_id}")
                    task_status = status_response.json()["status"]
                    
                    if task_status == "SUCCESS":
                        progress_bar.progress(100)
                        status_text.success("Analyse Computer Vision terminée ! ✅")
                    elif task_status == "FAILURE":
                        status_text.error("Erreur lors de l'exécution du Worker Celery.")
                        st.stop()
                        
                # 4. Récupération du rapport généré par le LLM (Ollama)
                with st.spinner("Génération du rapport d'expertise par le LLM..."):
                    report_response = requests.get(f"{API_URL}/report/")
                    if report_response.status_code == 200:
                        report_data = report_response.json().get("coach_report", "")
                        
                        st.markdown("### 📋 Rapport du Coach IA")
                        st.info(report_data)
            else:
                st.error("L'API FastAPI est injoignable.")

        with col2:
            st.subheader("📺 Radar Tactique & Tracking")
            # 5. Affichage du rendu visuel final
            video_resultat_path = "data/processed/radar_tactique.mp4"
            if os.path.exists(video_resultat_path):
                st.video(video_resultat_path)
            else:
                st.warning("La vidéo annotée n'est pas encore disponible.")