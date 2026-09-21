import numpy as np
from scipy.spatial import ConvexHull
import json
import os

class TacticalStateEngine:
    def __init__(self):
        """
        Initialise le moteur d'état tactique.
        Stocke l'historique complet pour pouvoir exporter la donnée à la fin de la vidéo.
        """
        self.historique_match = []

        # --- MÉMOIRE DE POSSESSION ---
        self.possession_actuelle = "UNKNOWN"
        self.frames_consecutives_possession = 0
        self.distance_controle_max = 2.5 # En mètres
        self.frames_confirmation = 3     # Nombre de frames pour valider un changement
        self.debut_possession_timestamp = 0.0

        # REGISTRE DES ÉVÉNEMENTS TACTIQUES ---
        self.evenements_match = []
        self.transitions_actives = {"A": None, "B": None} # Pour suivre le début/fin des phases
    
    def evaluer_evenements(self, timestamp, ancienne_possession):
        """
        Analyse la frame actuelle pour ouvrir ou fermer des événements tactiques.
        """
        # 1. ÉVÉNEMENT : Perte et Récupération de balle (Turnover)
        if ancienne_possession in ["A", "B"] and self.possession_actuelle in ["A", "B"] and ancienne_possession != self.possession_actuelle:
            # On enregistre la récupération
            self.evenements_match.append({
                "event": "ball_recovery",
                "team": self.possession_actuelle,
                "timestamp": round(timestamp, 2),
                "confidence": 0.95
            })
            # On enregistre la perte
            self.evenements_match.append({
                "event": "ball_loss",
                "team": ancienne_possession,
                "timestamp": round(timestamp, 2),
                "confidence": 0.95
            })

        # 2. ÉVÉNEMENT : Transition Défensive (Repli du bloc)
        for team_id in ["A", "B"]:
            if len(self.historique_match) == 0:
                continue
                
            etat_actuel = self.historique_match[-1]["teams"].get(team_id)
            if not etat_actuel: 
                continue
            
            phase_actuelle = etat_actuel.get("tactical_phase")
            transition_active = self.transitions_actives.get(team_id)
            
            # Cas A : La transition vient de commencer (Ouverture de l'événement)
            if phase_actuelle == "TRANSITION_DEFENSE" and not transition_active:
                self.transitions_actives[team_id] = {
                    "start_time": timestamp,
                    "initial_area": etat_actuel["compactness"]["convex_hull_area"],
                    "max_area": etat_actuel["compactness"]["convex_hull_area"]
                }
                
            # Cas B : La transition est en cours (Mise à jour des preuves/evidences)
            elif phase_actuelle == "TRANSITION_DEFENSE" and transition_active:
                area = etat_actuel["compactness"]["convex_hull_area"]
                # Si le bloc s'écarte encore plus, on sauvegarde le pire moment
                if area > transition_active["max_area"]:
                    transition_active["max_area"] = area
                    
            # Cas C : La transition est terminée (Fermeture et sauvegarde)
            elif phase_actuelle != "TRANSITION_DEFENSE" and transition_active:
                duree = timestamp - transition_active["start_time"]
                expansion = transition_active["max_area"] - transition_active["initial_area"]
                
                # Un repli doit durer un minimum de temps pour être significatif tactiquement
                if duree >= 1.5: 
                    self.evenements_match.append({
                        "event": "defensive_transition",
                        "team": team_id,
                        "timestamp": round(transition_active["start_time"], 2),
                        "duration": round(duree, 2),
                        "confidence": 0.88,
                        "evidence": {
                            "ball_loss": True,
                            "block_expansion_sqm": round(expansion, 2), # Preuve mathématique de la désorganisation
                            "recovery_time": round(duree, 2)
                        }
                    })
                # On réinitialise le traqueur
                self.transitions_actives[team_id] = None
    
    def estimer_vitesse_bloc(self, team_id, timestamp_actuel, fenetre_secondes=2.0):
        """
        Calcule la vélocité et l'expansion du bloc sur les X dernières secondes.
        Retourne la variation de la distance (dx, dy) et de la surface.
        """
        if len(self.historique_match) < 10:
            return 0.0, 0.0, 0.0 # Pas assez d'historique
            
        # Chercher l'état du bloc il y a 'fenetre_secondes'
        etat_passe = None
        for etat in reversed(self.historique_match):
            if timestamp_actuel - etat["timestamp"] >= fenetre_secondes:
                etat_passe = etat
                break
                
        if not etat_passe or team_id not in etat_passe.get("teams", {}):
            return 0.0, 0.0, 0.0
            
        etat_present = self.historique_match[-1]["teams"].get(team_id)
        if not etat_present:
            return 0.0, 0.0, 0.0
            
        # Calcul des dérivées (Deltas)
        delta_t = timestamp_actuel - etat_passe["timestamp"]
        dx = (etat_present["centroid"]["x"] - etat_passe["teams"][team_id]["centroid"]["x"]) / delta_t
        dy = (etat_present["centroid"]["y"] - etat_passe["teams"][team_id]["centroid"]["y"]) / delta_t
        delta_surface = (etat_present["compactness"]["convex_hull_area"] - etat_passe["teams"][team_id]["compactness"]["convex_hull_area"]) / delta_t
        
        return dx, dy, delta_surface

    def determiner_phase_equipe(self, team_id, timestamp):
        """
        Croise la possession, le temps et la cinématique du bloc pour déduire la phase de jeu.
        """
        duree_possession = timestamp - self.debut_possession_timestamp
        dx, dy, delta_surface = self.estimer_vitesse_bloc(team_id, timestamp)
        
        vitesse_bloc_absolue = np.linalg.norm([dx, dy])
        
        if self.possession_actuelle == team_id:
            # L'équipe A LE BALLON (Phases Offensives)
            if duree_possession < 5.0 and vitesse_bloc_absolue > 2.0:
                # Balle récupérée récemment + Bloc en mouvement rapide = Contre-Attaque
                return "TRANSITION_ATTACK"
            else:
                # Possession installée
                return "ATTACK"
                
        elif self.possession_actuelle not in [team_id, "UNKNOWN"]:
            # L'équipe N'A PAS LE BALLON (Phases Défensives)
            if duree_possession < 5.0:
                # Perte de balle récente
                if vitesse_bloc_absolue > 1.5 or delta_surface > 20.0:
                    # Le bloc court pour se replier OU le bloc s'étire dangereusement (lignes brisées)
                    return "TRANSITION_DEFENSE"
                else:
                    # Perte de balle mais le bloc est déjà en place
                    return "DEFENSE"
            else:
                # Défense placée classique
                return "DEFENSE"
                
        return "UNKNOWN"

    def calculer_possession(self, ballon, joueurs_A, joueurs_B):
        """
        Détermine l'équipe en possession du ballon avec lissage temporel.
        """
        # 1. Si le ballon est invisible ou que sa confiance est trop faible, on garde l'état précédent
        if ballon is None or ballon['confidence'] < 0.2:
            return self.possession_actuelle
            
        coords_ballon = np.array([ballon['x'], ballon['y']])
        
        distance_min_A = float('inf')
        distance_min_B = float('inf')
        
        # 2. Chercher le joueur le plus proche dans l'Équipe A
        if len(joueurs_A) > 0:
            coords_A = np.array([[p['x'], p['y']] for p in joueurs_A])
            distances_A = np.linalg.norm(coords_A - coords_ballon, axis=1)
            distance_min_A = np.min(distances_A)
            
        # 3. Chercher le joueur le plus proche dans l'Équipe B
        if len(joueurs_B) > 0:
            coords_B = np.array([[p['x'], p['y']] for p in joueurs_B])
            distances_B = np.linalg.norm(coords_B - coords_ballon, axis=1)
            distance_min_B = np.min(distances_B)

        # 4. Logique de détermination avec seuil de contrôle
        equipe_la_plus_proche = "UNKNOWN"
        if distance_min_A < distance_min_B and distance_min_A <= self.distance_controle_max:
            equipe_la_plus_proche = "A"
        elif distance_min_B < distance_min_A and distance_min_B <= self.distance_controle_max:
            equipe_la_plus_proche = "B"
            
        # 5. Filtre de confirmation (Anti-bruit)
        if equipe_la_plus_proche == self.possession_actuelle:
            self.frames_consecutives_possession += 1
        elif equipe_la_plus_proche != "UNKNOWN":
            # Un adversaire touche la balle, mais on attend confirmation
            if self.frames_consecutives_possession <= -self.frames_confirmation:
                # Changement de possession validé !
                self.possession_actuelle = equipe_la_plus_proche
                self.frames_consecutives_possession = 1
            else:
                self.frames_consecutives_possession -= 1
                
        return self.possession_actuelle

    def calculer_metriques_equipe(self, team_id, joueurs_data, timestamp):
        """
        Calcule les métriques spatiales d'une équipe à un instant T.
        :param team_id: "A" ou "B"
        :param joueurs_data: Liste de dictionnaires [{'id': 4, 'x': 45.2, 'y': 30.1, 'vx': 2.1, 'vy': 0.5}, ...]
        :param timestamp: Temps en secondes depuis le début de la vidéo
        """
        if len(joueurs_data) == 0:
            return None

        # Extraction vectorisée des coordonnées pour la performance mathématique
        coords = np.array([[p['x'], p['y']] for p in joueurs_data])
        x_coords = coords[:, 0]
        y_coords = coords[:, 1]

        # 1. Barycentre (Centroid)
        centroid_x = np.mean(x_coords)
        centroid_y = np.mean(y_coords)

        # 2. Dimensions du bloc
        # En football, l'axe X (0-105m) représente la longueur du terrain, l'axe Y (0-68m) la largeur
        longueur_bloc = np.max(x_coords) - np.min(x_coords)
        largeur_bloc = np.max(y_coords) - np.min(y_coords)

        # 3. Compacité (Dispersion)
        # Calcul de la distance euclidienne de chaque joueur par rapport au barycentre
        distances_barycentre = np.linalg.norm(coords - np.array([centroid_x, centroid_y]), axis=1)
        dispersion_moyenne = np.mean(distances_barycentre)

        # 4. Compacité (Aire de l'enveloppe convexe)
        aire_convexe = 0.0
        # Il faut mathématiquement au moins 3 points pour créer un polygone 2D
        if len(coords) >= 3:
            try:
                hull = ConvexHull(coords)
                aire_convexe = hull.volume  # Dans SciPy 2D, 'volume' renvoie l'aire du polygone
            except Exception:
                # Cas rare : tous les joueurs sont parfaitement alignés sur une droite
                aire_convexe = 0.0 

        # Formatage strict selon le brief technique
        etat_equipe = {
            "timestamp": round(timestamp, 2),
            "team": team_id,
            "players_count": len(joueurs_data),
            "centroid": {
                "x": round(float(centroid_x), 2),
                "y": round(float(centroid_y), 2)
            },
            "length": round(float(longueur_bloc), 2),
            "width": round(float(largeur_bloc), 2),
            "compactness": {
                "convex_hull_area": round(float(aire_convexe), 2),
                "mean_dispersion": round(float(dispersion_moyenne), 2)
            }
        }
        
        return etat_equipe

    def agreger_frame(self, timestamp, joueurs_A, joueurs_B, ballon = None):
        """
        Reçoit les données brutes des deux équipes et du ballon, calcule les métriques et sauvegarde l'état global.
        """

        ancienne_possession = self.possession_actuelle
        equipe_possession = self.calculer_possession(ballon, joueurs_A, joueurs_B)
        
        # Mise à jour du chronomètre si la possession change officiellement
        if equipe_possession != ancienne_possession and equipe_possession != "UNKNOWN":
            self.debut_possession_timestamp = timestamp

        etat_frame = {
            "timestamp": round(timestamp, 2),
            "possession": equipe_possession,
            "ball": ballon,
            "teams": {}
        }
        
        metriques_A = self.calculer_metriques_equipe("A", joueurs_A, timestamp)
        if metriques_A:
            etat_frame["teams"]["A"] = metriques_A
            
        metriques_B = self.calculer_metriques_equipe("B", joueurs_B, timestamp)
        if metriques_B:
            etat_frame["teams"]["B"] = metriques_B
            
        self.historique_match.append(etat_frame)

        # CALCUL DES PHASES ---
        if metriques_A:
            etat_frame["teams"]["A"]["tactical_phase"] = self.determiner_phase_equipe("A", timestamp)
        if metriques_B:
            etat_frame["teams"]["B"]["tactical_phase"] = self.determiner_phase_equipe("B", timestamp)
        
        #  évalue les événements après avoir calculé les phases ---
        self.evaluer_evenements(timestamp, ancienne_possession)

        return etat_frame

    def exporter_donnees(self, filepath_state="data/processed/tactical_state.json", filepath_events="data/processed/tactical_events.json"):
        """
        Exporte l'historique brut et les événements consolidés.
        """
        os.makedirs(os.path.dirname(filepath_state), exist_ok=True)
        
        # 1. Export du flux continu
        with open(filepath_state, 'w') as f:
            json.dump(self.historique_match, f, indent=4)
            
        # 2. Export du résumé tactique narratif
        with open(filepath_events, 'w') as f:
            json.dump(self.evenements_match, f, indent=4)
            
        print(f"💾 État tactique sauvegardé dans {filepath_state}")
        print(f"🎯 Événements tactiques sauvegardés dans {filepath_events}")