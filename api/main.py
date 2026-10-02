from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from api.worker import analyser_video_task
from src.llm.coach_agent import TacticalCoachAgent
from celery.result import AsyncResult
from api.worker import celery_app
from api.database import engine, Base, get_db
from api.storage import init_bucket, upload_stream
import api.models as models

# Création automatique des tables au démarrage de l'API
Base.metadata.create_all(bind=engine)

app = FastAPI(title="TacticalTwin AI API")
agent_coach = TacticalCoachAgent(model_name="mistral")

# Initialisation du Bucket S3
init_bucket()

# --- MIDDLEWARE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Autorise uniquement votre frontend
    allow_credentials=True,
    allow_methods=["*"], # Autorise POST, GET, OPTIONS, etc.
    allow_headers=["*"],
)

@app.post("/analyze/")
async def analyze_match(video: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Reçoit le fichier vidéo, l'uploade sur S3, crée un enregistrement en BDD 
    et délègue le traitement GPU à Celery.
    """
    # 1. Upload vers S3 (MinIO)
    s3_key = upload_stream(video.file, video.filename)

    # 2. Déclenchement du Worker Celery avec la clé S3 (.delay() envoie l'ordre à Redis de manière asynchrone)
    task = analyser_video_task.delay(s3_key)
    
    # 3. Enregistrement initial dans PostgreSQL
    db_match = models.MatchAnalysis(
        id=task.id,
        filename=video.filename,
        status="PENDING"
    )
    db.add(db_match)
    db.commit()
    
    return {
        "message": "Vidéo sécurisée sur S3, analyse asynchrone démarrée.",
        "task_id": task.id,
        "s3_key": s3_key
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
async def get_task_status(task_id: str, db: Session = Depends(get_db)):
    """
    Vérifie l'état de l'analyse dans PostgreSQL. Permet au frontend de vérifier si le Worker a terminé.
    """
    match = db.query(models.MatchAnalysis).filter(models.MatchAnalysis.id == task_id).first()
    
    if not match:
        return {"status": "NOT_FOUND"}
        
    return {
        "task_id": match.id,
        "status": match.status, # PENDING, SUCCESS, ou FAILED
        "coach_report": match.coach_report
    }