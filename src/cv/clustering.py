import cv2
import numpy as np
from sklearn.cluster import KMeans
from collections import Counter

class TeamClassifier:
    def __init__(self):
        """
        Gère l'assignation des équipes avec mémoire (Cache) et ancrage colorimétrique.
        """
        self.reference_colors = None  # Stockera les deux couleurs officielles [Couleur_A, Couleur_B]
        self.id_team_map = {}         # Dictionnaire mémoire : {track_id: team_id}

    def extraire_couleur_dominante(self, image_source, box):
        """
        Extrait la signature colorimétrique du maillot en ignorant la pelouse.
        Version ultra-optimisée sans KMeans individuel (Gain de FPS massif).
        """
        x1, y1, x2, y2 = map(int, box)
        w, h = x2 - x1, y2 - y1
        
        # 1. Ciblage strict du torse (Poitrine) - Évite les bras, le short et l'herbe
        y_haut = max(0, int(y1 + h * 0.15))
        y_bas = int(y1 + h * 0.45)
        x_gauche = max(0, int(x1 + w * 0.3))
        x_droite = int(x1 + w * 0.7)
        
        patch = image_source[y_haut:y_bas, x_gauche:x_droite]
        
        if patch.size == 0:
            return np.array([0, 0, 0])
            
        # 2. Conversion HSV pour isoler la teinte
        patch_hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
        
        # 3. Création du masque pour IGNORER la pelouse
        # Le vert en HSV se situe globalement entre les teintes 35 et 85
        masque_vert = cv2.inRange(patch_hsv, np.array([35, 20, 20]), np.array([85, 255, 255]))
        masque_non_vert = cv2.bitwise_not(masque_vert) # On garde tout ce qui N'EST PAS vert
        
        pixels_utiles = patch_hsv[masque_non_vert > 0]
        
        if len(pixels_utiles) == 0:
            # Sécurité : Si le patch était 100% vert (ex: joueur couché sur l'herbe)
            return np.mean(patch_hsv.reshape(-1, 3), axis=0)
            
        # 4. On retourne la vraie couleur moyenne du maillot
        return np.mean(pixels_utiles, axis=0)

    def get_teams(self, image_source, boxes_joueurs, track_ids):
        """
        Renvoie la liste des équipes (0 ou 1) synchronisée avec les boxes fournies.
        Gère les nouveaux IDs, les retours de joueurs, et optimise via le cache.
        """
        nouvelles_couleurs = []
        nouveaux_ids = []
        
        # 1. On vérifie qui est nouveau et qui est déjà connu
        for box, track_id in zip(boxes_joueurs, track_ids):
            if track_id not in self.id_team_map:
                # C'est un nouveau joueur (ou un retour de hors-champ)
                couleur = self.extraire_couleur_dominante(image_source, box)
                nouvelles_couleurs.append(couleur)
                nouveaux_ids.append(track_id)

        # 2. CALIBRATION (Se déclenche généralement une seule fois au début)
        # S'il nous manque les signatures globales et qu'on a assez de joueurs sur l'image
        if self.reference_colors is None and len(nouvelles_couleurs) >= 10:
            kmeans_global = KMeans(n_clusters=2, random_state=42, n_init=10)
            kmeans_global.fit(nouvelles_couleurs)
            self.reference_colors = kmeans_global.cluster_centers_

        # 3. MATCHING des nouveaux joueurs
        if self.reference_colors is not None and len(nouveaux_ids) > 0:
            for tid, couleur in zip(nouveaux_ids, nouvelles_couleurs):
                # Distance mathématique entre la couleur du joueur et les 2 maillots de référence
                dist_0 = np.linalg.norm(couleur - self.reference_colors[0])
                dist_1 = np.linalg.norm(couleur - self.reference_colors[1])
                
                # Assignation au maillot le plus proche
                self.id_team_map[tid] = 0 if dist_0 < dist_1 else 1

        # 4. GÉNÉRATION de la liste de sortie synchronisée
        labels_sortie = []
        for track_id in track_ids:
            # Si pour une raison rare on n'a pas encore de référence (ex: 2 joueurs sur la 1ere frame), on force à 0
            labels_sortie.append(self.id_team_map.get(track_id, 0))
            
        return labels_sortie