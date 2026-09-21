import cv2
import numpy as np

# Configuration d'un terrain standard (105m x 68m)
# Les clés (0, 1, 2...) correspondent à l'ordre des points dans le dataset YOLO-Pose
def generer_vrais_points(longueur=105.0, largeur=68.0):
    """
    Génère automatiquement les 32 points clés officiels du dataset Roboflow
    en utilisant les dimensions du terrain (par défaut UEFA : 105x68m).
    """
    # Dimensions standards du football (en mètres)
    w_pen = 40.32  # Largeur de la surface de réparation
    l_pen = 16.5   # Longueur (profondeur) de la surface de réparation
    w_but = 18.32  # Largeur de la surface de but (les 6 mètres)
    l_but = 5.5    # Longueur de la surface de but
    r_rond = 9.15  # Rayon du rond central
    d_pen = 11.0   # Distance du point de penalty

    points = [
        # --- CÔTÉ GAUCHE ---
        [0, 0], # 0: Poteau de corner Haut-Gauche
        [0, (largeur - w_pen) / 2], # 1: Ligne de but - Haut surface réparation
        [0, (largeur - w_but) / 2], # 2: Ligne de but - Haut surface but
        [0, (largeur + w_but) / 2], # 3: Ligne de but - Bas surface but
        [0, (largeur + w_pen) / 2], # 4: Ligne de but - Bas surface réparation
        [0, largeur], # 5: Poteau de corner Bas-Gauche
        
        [l_but, (largeur - w_but) / 2], # 6: Coin Haut-Droite surface de but
        [l_but, (largeur + w_but) / 2], # 7: Coin Bas-Droite surface de but
        
        [d_pen, largeur / 2], # 8: Point de penalty
        
        [l_pen, (largeur - w_pen) / 2], # 9: Coin Haut-Droite surface réparation
        [l_pen, (largeur - w_but) / 2], # 10: Intersection ligne réparation / surface but (Haut)
        [l_pen, (largeur + w_but) / 2], # 11: Intersection ligne réparation / surface but (Bas)
        [l_pen, (largeur + w_pen) / 2], # 12: Coin Bas-Droite surface réparation
        
        # --- LIGNE MÉDIANE ---
        [longueur / 2, 0], # 13: Ligne médiane / Ligne de touche Haute
        [longueur / 2, largeur / 2 - r_rond], # 14: Haut du rond central
        [longueur / 2, largeur / 2 + r_rond], # 15: Bas du rond central
        [longueur / 2, largeur], # 16: Ligne médiane / Ligne de touche Basse
        
        # --- CÔTÉ DROIT (Symétrie) ---
        [longueur - l_pen, (largeur - w_pen) / 2], # 17: Coin Haut-Gauche surface réparation
        [longueur - l_pen, (largeur - w_but) / 2], # 18: ...
        [longueur - l_pen, (largeur + w_but) / 2], # 19: ...
        [longueur - l_pen, (largeur + w_pen) / 2], # 20: Coin Bas-Gauche surface réparation
        
        [longueur - d_pen, largeur / 2], # 21: Point de penalty (Droite)
        
        [longueur - l_but, (largeur - w_but) / 2], # 22: Coin Haut-Gauche surface de but
        [longueur - l_but, (largeur + w_but) / 2], # 23: Coin Bas-Gauche surface de but
        
        [longueur, 0], # 24: Poteau de corner Haut-Droit
        [longueur, (largeur - w_pen) / 2], # 25: Ligne de but droite - Haut surface réparation
        [longueur, (largeur - w_but) / 2], # 26: ...
        [longueur, (largeur + w_but) / 2], # 27: ...
        [longueur, (largeur + w_pen) / 2], # 28: Ligne de but droite - Bas surface réparation
        [longueur, largeur], # 29: Poteau de corner Bas-Droit
        
        # --- POINTS LATÉRAUX DU ROND CENTRAL ---
        [longueur / 2 - r_rond, largeur / 2], # 30: Côté Gauche du rond central
        [longueur / 2 + r_rond, largeur / 2], # 31: Côté Droit du rond central
    ]
    
    # Transforme la liste en dictionnaire {0: [x, y], 1: [x, y]...}
    return {i: coord for i, coord in enumerate(points)}

VRAIS_POINTS_TERRAIN = generer_vrais_points()

def calculer_matrice_h(resultats_pose, seuil_confiance=0.6):
    """
    Extrait les points clés de l'image et calcule la matrice d'homographie H.
    """

    # --- GARDE-FOU ROBUSTE ---
    # On vérifie que la liste des résultats n'est pas vide ET que des keypoints ont été trouvés
    if len(resultats_pose) == 0 or resultats_pose[0].keypoints is None or len(resultats_pose[0].keypoints.data) == 0:
        return None, 0
    
    # YOLOv8-pose stocke les points sous la forme (x, y, confiance)
    # Shape: (Nombre_de_personnes/terrains, Nombre_de_points, 3)
    points_detectes = resultats_pose[0].keypoints.data[0].cpu().numpy()
    
    points_image_valides = []
    points_terrain_valides = []
    
    for index_point, (x, y, confiance) in enumerate(points_detectes):
        # On ne garde que les points dont l'IA est certaine et qui existent dans notre dictionnaire
        if confiance > seuil_confiance and index_point in VRAIS_POINTS_TERRAIN:
            points_image_valides.append([x, y])
            points_terrain_valides.append(VRAIS_POINTS_TERRAIN[index_point])
            
    # Il faut mathématiquement au moins 4 points pour une homographie
    if len(points_image_valides) >= 4:
        src_pts = np.array(points_image_valides, dtype=np.float32)
        dst_pts = np.array(points_terrain_valides, dtype=np.float32)
        
        # cv2.RANSAC est crucial ici pour éliminer les points aberrants
        H, masque = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        return H, len(points_image_valides)
        
    # Si la caméra a trop zoomé et qu'on voit moins de 4 points
    return None, len(points_image_valides)