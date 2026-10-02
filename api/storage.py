import boto3
from botocore.exceptions import ClientError
import uuid

# Configuration MinIO locale (Doit correspondre aux identifiants du docker-compose)
MINIO_ENDPOINT = "http://localhost:9000"
MINIO_ACCESS_KEY = "admin"
MINIO_SECRET_KEY = "password123"
BUCKET_NAME = "tactical-videos"

# Initialisation du client S3 (boto3)
s3_client = boto3.client(
    "s3",
    endpoint_url=MINIO_ENDPOINT,
    aws_access_key_id=MINIO_ACCESS_KEY,
    aws_secret_access_key=MINIO_SECRET_KEY,
)

def init_bucket():
    """Vérifie l'existence du bucket 'tactical-videos' et le crée si nécessaire."""
    try:
        s3_client.head_bucket(Bucket=BUCKET_NAME)
    except ClientError:
        s3_client.create_bucket(Bucket=BUCKET_NAME)
        print(f"🪣 Bucket S3 '{BUCKET_NAME}' créé avec succès.")

def upload_stream(file_obj, original_filename: str) -> str:
    """
    Prend le flux binaire reçu par FastAPI et l'envoie directement sur MinIO.
    Retourne une clé S3 (nom de fichier unique).
    """
    extension = original_filename.split('.')[-1]
    s3_key = f"{uuid.uuid4()}.{extension}"
    
    s3_client.upload_fileobj(file_obj, BUCKET_NAME, s3_key)
    return s3_key

def download_video(s3_key: str, download_path: str):
    """Télécharge une vidéo depuis MinIO vers le disque local du Worker Celery."""
    s3_client.download_file(BUCKET_NAME, s3_key, download_path)
    return download_path