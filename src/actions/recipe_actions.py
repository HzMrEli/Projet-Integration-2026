from __future__ import annotations

import json
from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

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

class ActionTellRecipeStep(Action):
    def name(self) -> Text:
        return "action_tell_recipe_step"

    def _extract_steps(self, tracker: Tracker) -> List[Dict[str, Any]]:
        steps_slot = tracker.get_slot("recipe_steps")
        if isinstance(steps_slot, list) and steps_slot:
            return steps_slot

        # Fallbacks: allow storing the full recipe card JSON in a slot.
        for slot_name in ("recipe_card", "recipe_json", "last_recipe", "recipe"):
            raw = tracker.get_slot(slot_name)
            if raw is None:
                continue

            if isinstance(raw, dict):
                data = raw
            elif isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
            else:
                continue

            recipe = data.get("recipe") if isinstance(data, dict) else None
            steps = recipe.get("steps") if isinstance(recipe, dict) else None
            if isinstance(steps, list) and steps:
                return steps

        return []

    def _get_int_slot(self, tracker: Tracker, slot_name: str, default: int = 0) -> int:
        val = tracker.get_slot(slot_name)
        if val is None:
            return default
        try:
            # Rasa float slots often store numbers as float.
            return int(float(val))
        except Exception:
            return default

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        steps = self._extract_steps(tracker)
        if not steps:
            dispatcher.utter_message(
                text="Je n'ai pas encore de recette en mémoire. Demande d'abord une recette, puis dis 'étape par étape'."
            )
            return []

        intent_name = (
            (tracker.latest_message or {}).get("intent") or {}
        ).get("name")

        current_index = self._get_int_slot(tracker, "step_index", default=0)

        if intent_name == "start_step_by_step":
            idx = 0
        elif intent_name == "repeat_step":
            last_text = tracker.get_slot("last_step_text")
            if isinstance(last_text, str) and last_text.strip():
                dispatcher.utter_message(text=last_text)
                return []
            idx = max(current_index - 1, 0)
        else:
            idx = max(current_index, 0)

        if idx >= len(steps):
            dispatcher.utter_message(text="C'est terminé : tu as déjà fait toutes les étapes.")
            return [SlotSet("step_index", float(len(steps)))]

        step = steps[idx] if isinstance(steps[idx], dict) else {}
        step_number = step.get("index")
        instruction = step.get("instruction")
        timer_min = step.get("timer_min")

        if not isinstance(instruction, str) or not instruction.strip():
            dispatcher.utter_message(text="Je n'arrive pas à lire cette étape. Dis 'suivant' pour passer à la prochaine.")
            return [SlotSet("step_index", float(idx + 1))]

        prefix = "Étape"
        if isinstance(step_number, int):
            text = f"{prefix} {step_number}: {instruction.strip()}"
        else:
            text = f"{prefix} {idx + 1}: {instruction.strip()}"

        try:
            timer_int = int(timer_min) if timer_min is not None else None
        except Exception:
            timer_int = None

        if timer_int is not None and timer_int > 0:
            text = f"{text} (environ {timer_int} min)"

        dispatcher.utter_message(text=text)

        return [
            SlotSet("step_index", float(idx + 1)),
            SlotSet("last_step_text", text),
        ]
