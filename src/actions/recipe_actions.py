from __future__ import annotations

import json
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher

from .openai_helpers import call_openai_json
from .schemas import RECIPE_SCHEMA


class ActionGenerateRecipeFromIngredients(Action):
    def name(self) -> Text:
        return "action_generate_recipe_from_ingredients"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        ingredients = tracker.get_slot("liste_ingredients")
        contraintes = tracker.get_slot("contraintes")
        temps_max = tracker.get_slot("temps_max")
        nb_personnes = tracker.get_slot("nb_personnes")

        prompt = (
            "Tu es un assistant de cuisine. Tu dois répondre UNIQUEMENT en JSON valide, "
            "sans texte autour. La réponse doit respecter exactement le schéma demandé.\n\n"
            "Contexte utilisateur: il donne des ingrédients disponibles, et veut une recette faisable.\n\n"
            f"Ingrédients disponibles: {ingredients}\n"
            f"Contraintes (optionnel): {contraintes}\n"
            f"Temps max (optionnel): {temps_max}\n"
            f"Nombre de personnes (optionnel): {nb_personnes}\n"
        )

        try:
            data = call_openai_json(prompt, schema=RECIPE_SCHEMA)
        except RuntimeError as exc:
            dispatcher.utter_message(text=str(exc))
            return []
        except Exception as exc:
            dispatcher.utter_message(text=f"Erreur lors de l'appel OpenAI: {exc}")
            return []

        dispatcher.utter_message(
            text=json.dumps(data, ensure_ascii=False),
            json_message=data,
        )
        return []


class ActionGenerateRecipeFromName(Action):
    def name(self) -> Text:
        return "action_generate_recipe_from_name"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        nom_recette = tracker.get_slot("nom_recette")
        nb_personnes = tracker.get_slot("nb_personnes")
        temps_max = tracker.get_slot("temps_max")
        contraintes = tracker.get_slot("contraintes")
        difficulte = tracker.get_slot("difficulte")

        if not nom_recette:
            dispatcher.utter_message(
                text="Quelle recette veux-tu ? (ex: 'pâtes carbonara', 'gratin dauphinois')"
            )
            return []

        prompt = (
            "Tu es un assistant de cuisine. Tu dois répondre UNIQUEMENT en JSON valide, "
            "sans texte autour. La réponse doit respecter exactement le schéma demandé.\n\n"
            "Contexte utilisateur: il donne le NOM d'une recette, et veut une fiche complète.\n\n"
            f"Nom de la recette: {nom_recette}\n"
            f"Nombre de personnes (optionnel): {nb_personnes}\n"
            f"Temps max (optionnel): {temps_max}\n"
            f"Contraintes (optionnel): {contraintes}\n"
            f"Difficulté souhaitée (optionnel): {difficulte}\n"
        )

        try:
            data = call_openai_json(prompt, schema=RECIPE_SCHEMA)
        except RuntimeError as exc:
            dispatcher.utter_message(text=str(exc))
            return []
        except Exception as exc:
            dispatcher.utter_message(text=f"Erreur lors de l'appel OpenAI: {exc}")
            return []

        dispatcher.utter_message(
            text=json.dumps(data, ensure_ascii=False),
            json_message=data,
        )
        return []
