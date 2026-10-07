import unittest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.main import app, get_db
from api.database import Base
from api.models import MatchAnalysis, TacticalEvent

# Setup an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

class TestAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        cls.client = TestClient(app)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        # Clear data before each test
        db = TestingSessionLocal()
        db.query(MatchAnalysis).delete()
        db.query(TacticalEvent).delete()
        db.commit()
        db.close()

    def test_get_matches_empty(self):
        response = self.client.get("/matches/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @patch("api.main.upload_stream")
    @patch("api.main.analyser_video_task.delay")
    def test_analyze_endpoint(self, mock_delay, mock_upload):
        # Mocking external services (S3 and Celery)
        mock_upload.return_value = "fake_s3_key"
        
        # mock celery task ID
        mock_task = MagicMock()
        mock_task.id = "fake_task_id"
        mock_delay.return_value = mock_task
        
        with open("test_video.mp4", "wb") as f:
            f.write(b"fake video data")
            
        with open("test_video.mp4", "rb") as f:
            response = self.client.post("/analyze/", files={"video": ("test_video.mp4", f, "video/mp4")})
            
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["task_id"], "fake_task_id")
        
        # Check database
        response = self.client.get("/matches/")
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(response.json()[0]["id"], "fake_task_id")

    def test_get_match_events(self):
        # Insert test data
        db = TestingSessionLocal()
        match = MatchAnalysis(id="test_match", filename="test.mp4", status="SUCCESS")
        event = TacticalEvent(match_id="test_match", timestamp=10.5, event_type="goal", team="A")
        db.add(match)
        db.add(event)
        db.commit()
        db.close()

        response = self.client.get("/matches/test_match/events")
        self.assertEqual(response.status_code, 200)
        events = response.json()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event_type"], "goal")

if __name__ == "__main__":
    unittest.main()

