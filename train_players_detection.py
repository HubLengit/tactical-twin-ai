from ultralytics import YOLO

# 1. Charger le modèle de base pré-entraîné (Nano, idéal pour itérer rapidement)
model = YOLO('yolov8n.pt')

# 2. Lancer l'entraînement
results = model.train(
    data='data/football-players-detection/data.yaml',             # Spécifiez le chemin exact vers votre fichier yaml téléchargé
    epochs=50,                    # 50 époques suffisent généralement pour un premier test
    imgsz=640,                    # Taille des images (standard pour YOLO)
    batch=16,                     # Taille du lot (réduisez à 8 si vous manquez de RAM/VRAM)
    name='tactical_twin_players', # Nom du dossier de sauvegarde
    patience=10                   # Arrêt anticipé : stoppe l'entraînement si le modèle ne s'améliore plus pendant 10 époques
)