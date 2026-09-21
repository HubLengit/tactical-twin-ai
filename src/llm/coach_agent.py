import json
import os
import ollama

class TacticalCoachAgent:
    def __init__(self, model_name="mistral"):
        """
        Agent IA agissant comme un analyste vidéo professionnel.
        Utilise Ollama en local pour garantir la confidentialité des données.
        """
        self.model = model_name

    def generer_rapport(self, events_filepath="data/processed/tactical_events.json"):
        if not os.path.exists(events_filepath):
            return "Erreur : Aucun fichier d'événements tactiques trouvé. Lancez d'abord l'analyse vidéo."
            
        with open(events_filepath, 'r') as f:
            evenements = json.load(f)
            
        if not evenements:
            return "Le rapport est vide, aucun événement tactique majeur n'a été détecté dans cette séquence."

        # 1. Formatage des données brutes en un contexte lisible pour le LLM
        contexte_donnees = "Voici les événements tactiques extraits par notre moteur de Computer Vision :\n\n"
        for ev in evenements:
            if ev["event"] == "ball_loss":
                contexte_donnees += f"- À {ev['timestamp']}s : Perte de balle de l'Équipe {ev['team']}.\n"
            elif ev["event"] == "ball_recovery":
                contexte_donnees += f"- À {ev['timestamp']}s : Récupération de balle par l'Équipe {ev['team']}.\n"
            elif ev["event"] == "defensive_transition":
                evidence = ev.get("evidence", {})
                contexte_donnees += (f"- À {ev['timestamp']}s : L'Équipe {ev['team']} subit une transition défensive. "
                                     f"Durée du repli : {ev['duration']} secondes. "
                                     f"Désorganisation (expansion du bloc) : {evidence.get('block_expansion_sqm', 0)} m² supplémentaires concédés.\n")

        # 2. Le Prompt Système Industriel (Garde-fous stricts)
        prompt_systeme = """Tu es un analyste tactique de football de niveau professionnel (ex: Data Analyst chez SkillCorner ou dans un grand club européen). 
Ton rôle est de lire les événements bruts issus de notre système de tracking et de rédiger un rapport clair, technique et concis pour l'entraîneur principal.

RÈGLES STRICTES :
1. Base-toi UNIQUEMENT sur les données fournies. N'invente aucun événement, aucun nom de joueur, et aucune action qui n'est pas dans le texte.
2. Explique l'impact des chiffres. Si un bloc s'étend de plus de 100m² lors d'une transition, explique que l'équipe s'étire dangereusement et offre des espaces.
3. Structure ton rapport avec des titres clairs (ex: 🔴 Pertes de Balle, 🛡️ Transitions Défensives, 💡 Conclusion / Recommandation).
4. Sois direct et utilise un vocabulaire métier (repli, compacité, déséquilibre, bloc équipe)."""

        # 3. Appel à l'API locale Ollama
        try:
            print(f"🧠 [LLM COACH] Génération du rapport via {self.model} en cours...")
            response = ollama.chat(model=self.model, messages=[
                {'role': 'system', 'content': prompt_systeme},
                {'role': 'user', 'content': contexte_donnees}
            ])
            return response['message']['content']
        except Exception as e:
            return f"Erreur lors de la communication avec Ollama : {str(e)}\nAssurez-vous que le service Ollama tourne en arrière-plan."