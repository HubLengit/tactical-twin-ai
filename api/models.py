from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from api.database import Base

class MatchAnalysis(Base):
    __tablename__ = "matches"

    id = Column(String, primary_key=True, index=True) # Sera le task_id de Celery
    filename = Column(String, nullable=False)
    status = Column(String, default="PENDING") # PENDING, PROCESSING, SUCCESS, FAILED
    coach_report = Column(String, nullable=True) # Le texte généré par l'Agent LLM
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    events = relationship("TacticalEvent", back_populates="match")

class TacticalEvent(Base):
    __tablename__ = "tactical_events"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(String, ForeignKey("matches.id"))
    timestamp = Column(Float, nullable=False)
    event_type = Column(String, nullable=False) # ex: ball_loss, defensive_transition
    team = Column(String, nullable=False)
    details = Column(JSON, nullable=True) # Stocke les preuves (block_expansion_sqm, etc.)

    match = relationship("MatchAnalysis", back_populates="events")