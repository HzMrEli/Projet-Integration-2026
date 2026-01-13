from __future__ import annotations

from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.events import EventType, SlotSet
from rasa_sdk.executor import CollectingDispatcher

from .audio import play_audio_local_async, truthy_env
from .openai_helpers import call_openai_tts


class ActionTextToSpeech(Action):
    def name(self) -> Text:
        return "action_text_to_speech"

    def get_last_bot_message(self, tracker: Tracker) -> Text | None:
        """Récupère le dernier message textuel envoyé par le bot."""
        for event in reversed(tracker.events):
            if event.get("event") == "bot" and event.get("text"):
                return event.get("text")
        return None

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[EventType]:

        # 1. Priorité aux slots explicites (définis par une Custom Action précédente)
        text = (
            tracker.get_slot("tts_text")
            or tracker.get_slot("texte_a_dire")
            or tracker.get_slot("texte")
        )

        # 2. Sinon, on lit le dernier message envoyé par le bot (cas des utter_...)
        if not text:
            text = self.get_last_bot_message(tracker)

        if not text or not str(text).strip():
            # Rien à lire
            return []

        try:
            result = call_openai_tts(str(text).strip())
        except Exception:
            # Action technique: avoid user-facing message
            return []

        if truthy_env("TTS_PLAY_AUDIO", default=True):
            play_audio_local_async(result["file_path"])

        # Optional: emit payload to channel if needed
        if truthy_env("TTS_EMIT_MESSAGE", default=True):
            payload = {
                "tts": {
                    "text": result["text"],
                    "mime_type": result["mime_type"],
                    "audio_base64": result["audio_base64"],
                    "file_path": result["file_path"],
                    "model": result["model"],
                    "voice": result["voice"],
                }
            }
            dispatcher.utter_message(json_message=payload)

        return [SlotSet("tts_last_file", result["file_path"])]