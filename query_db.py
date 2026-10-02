from api.database import SessionLocal
import api.models as models

db = SessionLocal()
matches = db.query(models.MatchAnalysis).all()
for m in matches:
    print(f"ID: {m.id}, Status: {m.status}, Report: {m.coach_report[:20] if m.coach_report else None}")
