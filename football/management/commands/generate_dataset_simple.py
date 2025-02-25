import openai
import os
import json
from django.core.management.base import BaseCommand
from django.utils.timezone import now
from football.models import QuestionTheme, Question

# Charger la clé OpenAI depuis les variables d'environnement
openai.api_key = os.getenv("OPENAI_API_KEY")

# Structure des thèmes
THEMES = [
    {"name": "Informations sur les matchs", "description": "Questions sur les matchs, horaires, stades et résultats."},
    {"name": "Informations sur les joueurs", "description": "Questions sur les joueurs, leurs statistiques et performances."},
    {"name": "Classements des équipes", "description": "Questions sur les classements et performances d'équipes."},
    {"name": "Historique des confrontations", "description": "Questions sur les rencontres passées entre deux équipes."},
    {"name": "Statistiques avancées", "description": "Questions détaillées sur les performances des équipes et joueurs."}
]

class Command(BaseCommand):
    help = "Génère un dataset de questions simples et les enregistre en base."

    def handle(self, *args, **kwargs):
        self.stdout.write("🔍 Initialisation de la génération de questions...")
        
        # Vérifier et insérer les thèmes
        for theme_data in THEMES:
            theme, created = QuestionTheme.objects.get_or_create(
                name=theme_data["name"],
                defaults={"description": theme_data["description"], "created_at": now()}
            )
            if created:
                self.stdout.write(f"✅ Thème ajouté : {theme.name}")

        # Générer les questions pour chaque thème
        for theme in QuestionTheme.objects.all():
            self.stdout.write(f"📝 Génération de questions pour le thème : {theme.name}")

            prompt = f"""
            Génère 10 questions simples en français pour le thème "{theme.name}" en utilisant différents styles d'écriture.
            - Varie les formulations mais garde la même intention.
            - Ne crée pas de questions nécessitant des calculs avancés.
            - Chaque question doit être compréhensible pour un humain cherchant une information spécifique.

            Exemples :
            - "Quels sont les matchs de Ligue 1 aujourd'hui ?"
            - "Donne-moi la liste des rencontres de Ligue 1 prévues aujourd’hui."

            Réponse attendue sous forme JSON :
            {{
                "questions": [
                    "Quels sont les matchs de Ligue 1 aujourd'hui ?",
                    "Donne-moi la liste des rencontres de Ligue 1 prévues aujourd’hui."
                ]
            }}
            """

            response = openai.ChatCompletion.create(
                model="gpt-4-turbo",
                messages=[{"role": "system", "content": "Tu es un assistant expert en bases de données et SQL."},
                          {"role": "user", "content": prompt}]
            )

            try:
                questions_json = json.loads(response["choices"][0]["message"]["content"])
                generated_questions = questions_json["questions"]
            except (KeyError, json.JSONDecodeError):
                self.stderr.write(f"❌ Erreur lors de la génération des questions pour {theme.name}")
                continue

            # Stocker les questions générées
            for question_text in generated_questions:
                question, created = Question.objects.get_or_create(
                    theme=theme,
                    text=question_text,
                    defaults={
                        "variations": [question_text],  # Initialement une seule variation
                        "complexity": "simple",
                        "created_at": now()
                    }
                )
                if created:
                    self.stdout.write(f"   ✅ Question ajoutée : {question.text}")

        self.stdout.write("🎉 Génération de dataset terminée avec succès !")
