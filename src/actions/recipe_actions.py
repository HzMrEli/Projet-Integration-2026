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
            dispatcher.utter_message(
                text=f"Erreur lors de l'appel OpenAI: {exc}")
            return []

        dump = json.dumps(data, ensure_ascii=False)

        recipe = data.get("recipe") if isinstance(data, dict) else None
        steps = recipe.get("instructions") if isinstance(recipe, dict) else None
        if not isinstance(steps, list):
            steps = []
        # Construction de formatted_ingredients pour l'affichage
        ingredients_data = recipe.get("ingredients", [])
        ingredients_str_list = []
        for ing in ingredients_data:
            i_name = ing.get("name", "")
            i_qty = ing.get("quantity")
            i_unit = ing.get("unit")
            
            # Format simple "quantity unit name" ou juste "name"
            if i_qty:
                if i_unit:
                    item_str = f"{i_qty} {i_unit} {i_name}"
                else:
                    item_str = f"{i_qty} {i_name}"
            else:
                item_str = i_name
            
            ingredients_str_list.append(item_str.strip())

        formatted_ingredients = ", ".join(ingredients_str_list)

        return [
            SlotSet("nom_recette", data["recipe"].get("name")),
            SlotSet("formatted_ingredients", formatted_ingredients),
            SlotSet("recipe_card", data),
            SlotSet("recipe_json", json.dumps(data, ensure_ascii=False)),
            SlotSet("recipe_steps", steps),
            SlotSet("step_index", 0.0),
            SlotSet("last_step_text", None),
        ]


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
            dispatcher.utter_message(
                text=f"Erreur lors de l'appel OpenAI: {exc}")
            return []
        
        dump = json.dumps(data, ensure_ascii=False)
        
        recipe = data.get("recipe") if isinstance(data, dict) else None
        steps = recipe.get("instructions") if isinstance(recipe, dict) else None
        if not isinstance(steps, list):
            steps = []

        # Construction de formatted_ingredients pour l'affichage
        ingredients_data = recipe.get("ingredients", [])
        ingredients_str_list = []
        for ing in ingredients_data:
            i_name = ing.get("name", "")
            i_qty = ing.get("quantity")
            i_unit = ing.get("unit")
            
            # Format simple "quantity unit name" ou juste "name"
            if i_qty:
                if i_unit:
                    item_str = f"{i_qty} {i_unit} {i_name}"
                else:
                    item_str = f"{i_qty} {i_name}"
            else:
                item_str = i_name
            
            ingredients_str_list.append(item_str.strip())

        formatted_ingredients = ""
        if ingredients_str_list:
            if len(ingredients_str_list) == 1:
                formatted_ingredients = ingredients_str_list[0]
            else:
                formatted_ingredients = ", ".join(ingredients_str_list[:-1]) + " et " + ingredients_str_list[-1]

        return [
            SlotSet("nom_recette", data["recipe"].get("name")),
            SlotSet("formatted_ingredients", formatted_ingredients),
            SlotSet("recipe_card", data),
            SlotSet("recipe_json", json.dumps(data, ensure_ascii=False)),
            SlotSet("recipe_steps", steps),
            SlotSet("step_index", 0.0),
            SlotSet("last_step_text", None),
        ]


class ActionTellRecipeStep(Action):
    def name(self) -> Text:
        return "action_tell_recipe_step"

    def _extract_steps(self, tracker: Tracker) -> List[Any]:
        steps_slot = tracker.get_slot("recipe_steps")
        if isinstance(steps_slot, list) and steps_slot:
            return steps_slot

        # Fallbacks: allow storing the full recipe card JSON in a slot.
        for slot_name in ("recipe_card", "recipe_json"):
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
            steps = recipe.get("instructions") if isinstance(recipe, dict) else None
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
            text = (
                "Je n'ai pas encore de recette en mémoire. "
                "Demande d'abord une recette, puis dis 'étape par étape'."
            )
            dispatcher.utter_message(text=text)
            return [SlotSet("tts_text", text)]

        intent_name = ((tracker.latest_message or {}).get("intent") or {}).get("name")
        current_index = self._get_int_slot(tracker, "step_index", default=0)

        if intent_name == "start_step_by_step":
            idx = 0
        elif intent_name == "repeat_step":
            last_text = tracker.get_slot("last_step_text")
            if isinstance(last_text, str) and last_text.strip():
                dispatcher.utter_message(text=last_text)
                return [SlotSet("tts_text", last_text)]
            idx = max(current_index - 1, 0)
        else:
            idx = max(current_index, 0)

        if idx >= len(steps):
            text = "C'est terminé : tu as déjà fait toutes les étapes."
            dispatcher.utter_message(text=text)
            return [
                SlotSet("step_index", float(len(steps))),
                SlotSet("tts_text", text)
            ]

        step_raw = steps[idx]
        if isinstance(step_raw, str):
            instruction = step_raw.strip()
        else:
            instruction = ""

        if not instruction:
            text = "Je n'arrive pas à lire cette étape. Dis 'suivant' pour passer à la prochaine."
            dispatcher.utter_message(text=text)
            return [
                SlotSet("step_index", float(idx + 1)),
                SlotSet("tts_text", text)
            ]

        text = f"Étape {idx + 1}: {instruction}"
        dispatcher.utter_message(text=text)

        return [
            SlotSet("step_index", float(idx + 1)),
            SlotSet("last_step_text", text),
            SlotSet("tts_text", text),
        ]


class ActionTellFullRecipe(Action):
    def name(self) -> Text:
        return "action_tell_full_recipe"

    def _load_recipe(self, tracker: Tracker) -> Dict[str, Any] | None:
        raw = tracker.get_slot("recipe_card") or tracker.get_slot("recipe_json")
        if raw is None:
            return None
        if isinstance(raw, dict):
            data = raw
        elif isinstance(raw, str):
            try:
                data = json.loads(raw)
            except Exception:
                return None
        else:
            return None

        recipe = data.get("recipe") if isinstance(data, dict) else None
        return recipe if isinstance(recipe, dict) else None

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        recipe = self._load_recipe(tracker)
        if not recipe:
            dispatcher.utter_message(
                text="Je n'ai pas encore de recette en mémoire. Demande d'abord une recette, puis redis-moi ce que tu veux."
            )
            return []

        name = recipe.get("name") or tracker.get_slot("nom_recette")
        servings = recipe.get("servings")
        times = recipe.get("times") if isinstance(recipe.get("times"), dict) else {}
        total_min = times.get("total_min")

        header_parts: List[str] = []
        if isinstance(name, str) and name.strip():
            header_parts.append(f"Recette : {name.strip()}")
        if isinstance(servings, int) and servings > 0:
            header_parts.append(f"pour {servings} personne(s)")
        if isinstance(total_min, int) and total_min > 0:
            header_parts.append(f"(temps total ~ {total_min} min)")

        header = " ".join(header_parts) if header_parts else "Recette complète"

        ingredients = recipe.get("ingredients")
        ing_lines: List[str] = []
        if isinstance(ingredients, list):
            for ing in ingredients:
                if not isinstance(ing, dict):
                    continue
                i_name = str(ing.get("name") or "").strip()
                if not i_name:
                    continue
                qty = ing.get("quantity")
                unit = ing.get("unit")
                if qty is None:
                    ing_lines.append(f"- {i_name}")
                else:
                    unit_str = f" {unit}" if isinstance(unit, str) and unit.strip() else ""
                    ing_lines.append(f"- {qty}{unit_str} {i_name}".strip())

        steps = recipe.get("instructions")
        step_lines: List[str] = []
        if isinstance(steps, list):
            for idx, s in enumerate(steps, start=1):
                if isinstance(s, str) and s.strip():
                    step_lines.append(f"{idx}. {s.strip()}")

        message_parts = [header]
        if ing_lines:
            message_parts.append("Ingrédients :\n" + "\n".join(ing_lines))
        if step_lines:
            message_parts.append("Étapes :\n" + "\n".join(step_lines))

        dispatcher.utter_message(text="\n\n".join(message_parts))
        return []
