"""Rasa custom actions entrypoint.

Rasa (action server) typically points to this module, so keep it as a stable entrypoint.
The implementation is split into smaller modules under `src/actions/`.
"""

# Actions (résumé rapide)
# - action_hello_world: pas d'entrée, utter "Hello World!".
# - action_generate_recipe_from_ingredients: slots {liste_ingredients, contraintes, temps_max, nb_personnes}; env {OPENAI_API_KEY, OPENAI_MODEL}; sort json_message conforme RECIPE_SCHEMA.
# - action_generate_recipe_from_name: slots {nom_recette, nb_personnes, temps_max, contraintes, difficulte}; env {OPENAI_API_KEY, OPENAI_MODEL}; sort json_message conforme RECIPE_SCHEMA.
# - action_text_to_speech: slots {tts_text|texte_a_dire|texte} (fallback latest_message.text); env {OPENAI_API_KEY, OPENAI_TTS_*, TTS_*}; sort SlotSet("tts_last_file"), lecture locale si TTS_PLAY_AUDIO=true.
# - action_ui_refresh_pronounce_phrase: pas d'entrée; sort SlotSet("ui_event"={type:"PRONOUNCE_PHRASE", text:"Je pronnonce cette phrase"}).

from __future__ import annotations

from .misc_actions import ActionHelloWorld
from .recipe_actions import ActionGenerateRecipeFromIngredients, ActionGenerateRecipeFromName
from .tts_actions import ActionTextToSpeech, ActionUiRefreshPronouncePhrase

__all__ = [
    "ActionHelloWorld",
    "ActionGenerateRecipeFromIngredients",
    "ActionGenerateRecipeFromName",
    "ActionTextToSpeech",
    "ActionUiRefreshPronouncePhrase",
]