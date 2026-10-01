from fastapi import FastAPI
from api.worker import analyser_video_task
from src.llm.coach_agent import TacticalCoachAgent
from celery.result import AsyncResult
from api.worker import celery_app
from api.database import engine, Base
import api.models

# Création automatique des tables au démarrage de l'API
Base.metadata.create_all(bind=engine)

app = FastAPI(title="TacticalTwin AI API")
agent_coach = TacticalCoachAgent(model_name="mistral")

@app.post("/analyze/")
async def analyze_match(video_path: str):
    """
    Route appelée par l'utilisateur. 
    Elle délègue immédiatement la tâche à Celery et libère la connexion.
    """
    # .delay() envoie l'ordre à Redis de manière asynchrone
    task = analyser_video_task.delay(video_path)
    
    return {
        "message": "Vidéo bien reçue, analyse en cours d'exécution en arrière-plan.", 
        "task_id": task.id
    }

@app.get("/report/")
async def get_tactical_report():
    """
    Lit le dernier fichier d'événements généré par le Worker 
    et fait générer une analyse métier par le LLM.
    """
    rapport_texte = agent_coach.generer_rapport()
    
    return {
        "status": "success",
        "coach_report": rapport_texte
    }


@app.get("/status/{task_id}")
async def get_task_status(task_id: str):
    """
    Permet au frontend (Streamlit) de vérifier si le Worker a terminé.
    """
    task_result = AsyncResult(task_id, app=celery_app)
    return {
        "task_id": task_id,
        "status": task_result.status, # "PENDING", "STARTED", "SUCCESS" ou "FAILURE"
    }