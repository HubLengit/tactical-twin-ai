import os
from celery import Celery
from api.storage import download_video
import cv2
import numpy as np
import torch
from ultralytics import YOLO
from src.cv.homography import calculer_matrice_h
from src.cv.tracking import CinematicTracker
from src.cv.tactical_state import TacticalStateEngine
from src.cv.clustering import TeamClassifier

# Connexion de Celery au broker Redis dans Docker
celery_app = Celery(
    "tactical_worker",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0"
)

@celery_app.task(bind=True)
def analyser_video_task(self, s3_key: str):
    """
    Télécharge la vidéo depuis S3 puis Tâche asynchrone Celery exécutant l'intégralité du pipeline de Computer Vision
    """
    print(f"⚙️ [WORKER] Démarrage de la tâche pour la vidéo S3 : {s3_key}")

    # 1. Téléchargement depuis MinIO vers un espace temporaire local du worker
    os.makedirs("data/raw", exist_ok=True)
    local_video_path = f"data/raw/{s3_key}"
    download_video(s3_key, local_video_path)
    
    # 1. Configuration du Device (Mac M2 - MPS)
    device = 'mps' if torch.backends.mps.is_available() else 'cpu'
    print(f"🚀 Moteur d'inférence activé dans le worker : {device.upper()}")

    # 2. Chargement des modèles et affectation au GPU
    modele_terrain = YOLO('runs/pose/train-3/weights/best.pt')
    modele_joueurs = YOLO('runs/detect/tactical_twin_players/weights/best.pt')

    modele_terrain.to(device)
    modele_joueurs.to(device)

    # 3. Initialisation de la vidéo
    if not os.path.exists(local_video_path):
        return {"status": "error", "message": f"Fichier vidéo introuvable : {local_video_path}"}

    cap = cv2.VideoCapture(local_video_path)
    fps_video = cap.get(cv2.CAP_PROP_FPS)
    if fps_video <= 0:
        fps_video = 30.0 # Valeur de repli sécurisée

    # Configuration de l'export vidéo annoté
    os.makedirs('data/processed', exist_ok=True)
    largeur = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    hauteur = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_video_path = 'data/processed/radar_tactique.mp4'
    out = cv2.VideoWriter(out_video_path, fourcc, fps_video, (largeur, hauteur))

    # Instanciation des modules d'analyse
    tracker_cinematique = CinematicTracker(fps=fps_video, lissage_frames=15)
    moteur_tactique = TacticalStateEngine()
    classificateur_equipes = TeamClassifier()

    frame_count = 0
    matrice_H_lisse = None
    alpha = 0.15

    print(f"Début de l'analyse vidéo à {fps_video} FPS...")

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        frame_count += 1
        
        # Étape A : Calibrage géométrique par homographie
        resultats_terrain = modele_terrain(frame, conf=0.1, verbose=False, device=device)
        matrice_H_nouvelle, _ = calculer_matrice_h(resultats_terrain)
        
        if matrice_H_nouvelle is not None:
            if matrice_H_lisse is None:
                matrice_H_lisse = matrice_H_nouvelle
            else:
                matrice_H_lisse = cv2.addWeighted(
                    matrice_H_nouvelle, alpha, 
                    matrice_H_lisse, 1 - alpha, 
                    0.0
                )

        if matrice_H_lisse is not None:
            # Étape B : Inférence YOLO & ByteTrack
            resultats_track = modele_joueurs.track(frame, persist=True, tracker="bytetrack.yaml", verbose=False, device=device)[0]
            image_originale = resultats_track.orig_img
            
            # Extraction et projection du ballon
            classes_toutes = resultats_track.boxes.cls.int().cpu().tolist()
            confidences = resultats_track.boxes.conf.cpu().tolist()
            boxes_toutes = resultats_track.boxes.xyxy.cpu().numpy()
            
            ballon_etat = None
            meilleure_confiance = 0.0
            
            for box, cls, conf in zip(boxes_toutes, classes_toutes, confidences):
                if cls == 0 and conf > meilleure_confiance:
                    meilleure_confiance = conf
                    x1, y1, x2, y2 = box
                    x_centre_ball = (x1 + x2) / 2
                    y_centre_ball = (y1 + y2) / 2
                    
                    pts_array = np.array([[[x_centre_ball, y_centre_ball]]], dtype=np.float32)
                    pts_2d = cv2.perspectiveTransform(pts_array, matrice_H_lisse)
                    x_ball_reel, y_ball_reel = pts_2d[0][0][0], pts_2d[0][0][1]
                    
                    if -5 <= x_ball_reel <= 110 and -5 <= y_ball_reel <= 73:
                        ballon_etat = {
                            "x": round(float(x_ball_reel), 2),
                            "y": round(float(y_ball_reel), 2),
                            "confidence": round(float(meilleure_confiance), 2)
                        }
                        cv2.circle(frame, (int(x_centre_ball), int(y_centre_ball)), 6, (255, 255, 255), -1)
                        cv2.circle(frame, (int(x_centre_ball), int(y_centre_ball)), 6, (0, 0, 0), 2)
                        cv2.putText(frame, f"{conf:.2f}", (int(x1), int(y1)-10), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

            # Suivi des joueurs et clustering d'équipe
            joueurs_A = []
            joueurs_B = []
            
            if resultats_track.boxes.id is not None:
                boxes = resultats_track.boxes.xyxy.cpu().numpy()
                track_ids = resultats_track.boxes.id.int().cpu().tolist()
                classes = resultats_track.boxes.cls.int().cpu().tolist()
                
                pixels_pieds_joueurs = []
                ids_joueurs = []
                boxes_joueurs = [] 

                for box, track_id, cls in zip(boxes, track_ids, classes):
                    if cls == 2:
                        x1, y1, x2, y2 = box
                        x_centre = (x1 + x2) / 2
                        y_pieds = y2
                        pixels_pieds_joueurs.append([x_centre, y_pieds])
                        ids_joueurs.append(track_id) 
                        boxes_joueurs.append(box)
                        
                if len(pixels_pieds_joueurs) > 0:
                    pts_array = np.array(pixels_pieds_joueurs, dtype=np.float32).reshape(-1, 1, 2)
                    pts_2d = cv2.perspectiveTransform(pts_array, matrice_H_lisse)
                    
                    labels_equipes = classificateur_equipes.get_teams(image_originale, boxes_joueurs, ids_joueurs)
                    
                    for index_synchronise, track_id in enumerate(ids_joueurs):
                        x_reel, y_reel = pts_2d[index_synchronise][0][0], pts_2d[index_synchronise][0][1]
                        x1, y1, x2, y2 = map(int, boxes_joueurs[index_synchronise])
                        
                        if -5 <= x_reel <= 110 and -5 <= y_reel <= 73:
                            vitesse = tracker_cinematique.mettre_a_jour_joueur(track_id, x_reel, y_reel)
                            equipe_id = labels_equipes[index_synchronise]
                            donnees_joueur = {
                                'id': track_id, 
                                'x': round(float(x_reel), 2), 
                                'y': round(float(y_reel), 2), 
                                'speed': vitesse
                            }
                            
                            if equipe_id == 0:
                                joueurs_A.append(donnees_joueur)
                                couleur_equipe = (255, 0, 0)
                            else:
                                joueurs_B.append(donnees_joueur)
                                couleur_equipe = (0, 0, 255)
                            
                            cv2.rectangle(frame, (x1, y1), (x2, y2), couleur_equipe, 2)
                            
                            if vitesse > 15.0:
                                epaisseur = 2 if vitesse > 25.0 else 1
                                cv2.putText(frame, f"{vitesse} km/h", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, couleur_equipe, epaisseur)

            # Agrégation dans le moteur d'état tactique
            temps_actuel_secondes = frame_count / fps_video
            moteur_tactique.agreger_frame(temps_actuel_secondes, joueurs_A, joueurs_B, ballon_etat)

        out.write(frame)

    cap.release()
    out.release() 

    # Exportation finale des fichiers JSON structurés
    state_path = "data/processed/tactical_state.json"
    events_path = "data/processed/tactical_events.json"
    moteur_tactique.exporter_donnees(state_path, events_path)
    
    print(f"✅ [WORKER] Analyse terminée avec succès pour {local_video_path}")
    return {
        "status": "success",
        "video_output": out_video_path,
        "state_json": state_path,
        "events_json": events_path
    }