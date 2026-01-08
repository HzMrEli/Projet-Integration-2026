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

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[EventType]:

        text = (
            tracker.get_slot("tts_text")
            or tracker.get_slot("texte_a_dire")
            or tracker.get_slot("texte")
            or (tracker.latest_message or {}).get("text")
        )

        if not text or not str(text).strip():
            # Action technique: no user message
            return []

        try:
            result = call_openai_tts(str(text).strip())
        except Exception:
            # Action technique: avoid user-facing message
            return []

        if truthy_env("TTS_PLAY_AUDIO", default=True):
            play_audio_local_async(result["file_path"])

        # Optional: emit payload to channel if needed
        if truthy_env("TTS_EMIT_MESSAGE", default=False):
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


class ActionUiRefreshPronouncePhrase(Action):
    def name(self) -> Text:
        return "action_ui_refresh_pronounce_phrase"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[EventType]:

        phrase = "Je pronnonce cette phrase"
        ui_event = {
            "type": "PRONOUNCE_PHRASE",
            "text": phrase,
        }

        return [SlotSet("ui_event", ui_event)]
