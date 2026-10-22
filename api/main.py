from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from api.worker import analyser_video_task
from src.llm.coach_agent import TacticalCoachAgent
from celery.result import AsyncResult
from api.worker import celery_app
from api.database import engine, Base, get_db
from api.storage import init_bucket, upload_stream
import api.models as models
import api.schemas as schemas
from api.auth import (
    get_password_hash, verify_password, create_access_token,
    get_current_user, ACCESS_TOKEN_EXPIRE_MINUTES
)
from typing import List

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

# --- AUTHENTICATION ROUTES ---
@app.post("/register", response_model=schemas.UserResponse)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_password = get_password_hash(user.password)
    new_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# --- PROTECTED ROUTES ---
@app.post("/analyze/")
async def analyze_match(
    video: UploadFile = File(...), 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Reçoit le fichier vidéo, l'uploade sur S3, crée un enregistrement en BDD 
    et délègue le traitement GPU à Celery.
    """
    # 1. Upload vers S3 (MinIO)
    s3_key = upload_stream(video.file, video.filename)

    # 2. Déclenchement du Worker Celery avec la clé S3 (.delay() envoie l'ordre à Redis de manière asynchrone)
    task = analyser_video_task.delay(s3_key)
    
    # 3. Enregistrement initial dans PostgreSQL lié à l'utilisateur connecté
    db_match = models.MatchAnalysis(
        id=task.id,
        filename=video.filename,
        status="PENDING",
        owner_id=current_user.id
    )
    db.add(db_match)
    db.commit()
    
    return {
        "message": "Vidéo sécurisée sur S3, analyse asynchrone démarrée.",
        "task_id": task.id,
        "s3_key": s3_key
    }

@app.get("/report/")
async def get_tactical_report(current_user: models.User = Depends(get_current_user)):
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
async def get_task_status(
    task_id: str, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Vérifie l'état de l'analyse dans PostgreSQL. Permet au frontend de vérifier si le Worker a terminé.
    """
    match = db.query(models.MatchAnalysis).filter(models.MatchAnalysis.id == task_id, models.MatchAnalysis.owner_id == current_user.id).first()
    
    if not match:
        raise HTTPException(status_code=404, detail="Match not found or unauthorized")
        
    return {
        "task_id": match.id,
        "status": match.status, # PENDING, SUCCESS, ou FAILED
        "coach_report": match.coach_report
    }


@app.get("/matches/", response_model=List[schemas.MatchResponse])
async def get_matches(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Retrieve all uploaded matches for the current user, ordered by creation date (newest first).
    """
    matches = db.query(models.MatchAnalysis).filter(models.MatchAnalysis.owner_id == current_user.id).order_by(models.MatchAnalysis.created_at.desc()).all()
    return matches

@app.get("/matches/{match_id}/events", response_model=List[schemas.TacticalEventResponse])
async def get_match_events(
    match_id: str, 
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """
    Retrieve all tactical events associated with a specific match.
    """
    # Vérifier que le match appartient bien à l'utilisateur
    match = db.query(models.MatchAnalysis).filter(models.MatchAnalysis.id == match_id, models.MatchAnalysis.owner_id == current_user.id).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found or unauthorized")

    events = db.query(models.TacticalEvent).filter(models.TacticalEvent.match_id == match_id).order_by(models.TacticalEvent.timestamp.asc()).all()
    return events