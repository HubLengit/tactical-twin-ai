import numpy as np
from collections import deque

class CinematicTracker:
    # On passe le lissage à 15 frames (environ 0.5s à 30 FPS) au lieu de 5
    def __init__(self, fps=30, lissage_frames=15):
        self.fps = fps
        self.lissage_frames = lissage_frames
        self.trajectoires = {}

    def mettre_a_jour_joueur(self, joueur_id, x_2d, y_2d):
        if joueur_id not in self.trajectoires:
            self.trajectoires[joueur_id] = deque(maxlen=self.lissage_frames)
            
        self.trajectoires[joueur_id].append(np.array([x_2d, y_2d]))
        
        historique = self.trajectoires[joueur_id]
        
        # On attend que le buffer soit plein pour avoir un calcul fiable
        if len(historique) == self.lissage_frames:
            # Pour lisser encore plus, on compare la moyenne des 3 premières frames 
            # avec la moyenne des 3 dernières frames
            pos_depart = np.mean(list(historique)[:3], axis=0)
            pos_arrivee = np.mean(list(historique)[-3:], axis=0)
            
            distance_metres = np.linalg.norm(pos_arrivee - pos_depart)
            
            # Le temps écoulé est la taille du buffer moins le lissage des fenêtres
            temps_secondes = (self.lissage_frames - 3) / self.fps
            
            vitesse_m_s = distance_metres / temps_secondes
            vitesse_km_h = vitesse_m_s * 3.6
            
            # On force la conversion en float natif et on arrondit à 1 décimale
            vitesse_finale = round(float(vitesse_km_h), 1)
            # On ignore les vitesses délirantes (> 45 km/h) qui sont des erreurs de tracking
            if vitesse_finale > 45.0:
                return 0.0
                
            return vitesse_finale
            
        return 0.0