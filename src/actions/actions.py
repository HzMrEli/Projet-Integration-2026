from __future__ import annotations

import base64
import json
import os
import platform
import threading
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher


class ActionHelloWorld(Action):

    def name(self) -> Text:
        return "action_hello_world"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="Hello World!")

        return []


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
            data = _call_openai_json(prompt, schema=_RECIPE_SCHEMA)
        except RuntimeError as exc:
            dispatcher.utter_message(text=str(exc))
            return []
        except Exception as exc:
            dispatcher.utter_message(text=f"Erreur lors de l'appel ChatGPT: {exc}")
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
            data = _call_openai_json(prompt, schema=_RECIPE_SCHEMA)
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


class ActionTextToSpeech(Action):
    def name(self) -> Text:
        return "action_text_to_speech"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> List[Dict[Text, Any]]:

        # Priority: explicit slot text; otherwise fallback to the latest user message.
        text = (
            tracker.get_slot("tts_text")
            or tracker.get_slot("texte_a_dire")
            or tracker.get_slot("texte")
            or (tracker.latest_message or {}).get("text")
        )

        if not text or not str(text).strip():
            dispatcher.utter_message(
                text="Quel texte veux-tu que je fasse énoncer ?",
            )
            return []

        try:
            result = _call_openai_tts(str(text).strip())
        except RuntimeError as exc:
            dispatcher.utter_message(text=str(exc))
            return []
        except Exception as exc:
            dispatcher.utter_message(text=f"Erreur lors de l'appel OpenAI TTS: {exc}")
            return []

        # Local playback on the machine running the action server (debug on PC).
        # Uses the default Windows audio output (your connected speaker if set as default).
        if _truthy_env("TTS_PLAY_AUDIO", default=True):
            _play_audio_local_async(result["file_path"])

        # Many Rasa channels can render/play an audio attachment via a custom payload.
        # We include base64 audio so the client can play it without hosting a file.
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

        dispatcher.utter_message(
            text=json.dumps(payload, ensure_ascii=False),
            json_message=payload,
        )
        return []


_RECIPE_SCHEMA: Dict[str, Any] = {
    "name": "recipe_card",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "recipe": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "name": {"type": "string"},
                    "servings": {"type": ["integer", "null"], "minimum": 1},
                    "times": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "total_min": {"type": "integer", "minimum": 1},
                            "prep_min": {"type": ["integer", "null"], "minimum": 0},
                            "cook_min": {"type": ["integer", "null"], "minimum": 0},
                        },
                        "required": ["total_min", "prep_min", "cook_min"],
                    },
                    "ingredients": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "name": {"type": "string"},
                                "quantity": {"type": ["number", "null"]},
                                "unit": {"type": ["string", "null"]},
                                "critical": {"type": "boolean"},
                                "alternative": {"type": ["string", "null"]},
                            },
                            "required": [
                                "name",
                                "quantity",
                                "unit",
                                "critical",
                                "alternative",
                            ],
                        },
                    },
                    "steps": {
                        "type": "array",
                        "minItems": 1,
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "index": {"type": "integer", "minimum": 1},
                                "instruction": {"type": "string"},
                                "timer_min": {"type": ["integer", "null"], "minimum": 0},
                            },
                            "required": ["index", "instruction", "timer_min"],
                        },
                    },
                },
                "required": ["name", "servings", "times", "ingredients", "steps"],
            }
        },
        "required": ["recipe"],
    },
}


def _call_openai_json(prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Appel OpenAI qui retourne un dict JSON (robuste).

    - Utilise `responses.create(..., response_format=json_schema)` si dispo.
    - Sinon fallback sur `chat.completions.create(..., response_format=json_object)`.

    Requis: variable d'environnement OPENAI_API_KEY.
    Optionnel: OPENAI_MODEL (défaut: gpt-4o-mini).
    """

    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "La librairie 'openai' n'est pas installée. Installe-la puis relance l'action server."
        ) from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY n'est pas défini. Configure la variable d'environnement et réessaie."
        )

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    client = OpenAI(api_key=api_key)

    system = (
        "Tu es un assistant de cuisine. "
        "Tu dois produire une sortie JSON STRICTE conforme au schéma. "
        "Ne mets jamais de texte hors JSON. "
        "Si une alternative n'existe pas, mets alternative=null. "
        "Si un ingrédient est critique, mets alternative=null."
    )

    text: Optional[str] = None
    try:
        # Preferred (more robust): Responses API with JSON schema
        if hasattr(client, "responses"):
            resp = client.responses.create(
                model=model,
                input=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": schema,
                },
                temperature=0.2,
            )
            text = getattr(resp, "output_text", None)
        else:
            raise AttributeError("responses API not available")
    except Exception:
        # Fallback: Chat Completions JSON mode
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        text = resp.choices[0].message.content

    if not text:
        raise RuntimeError("Réponse OpenAI vide.")

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        snippet = text[:500]
        raise RuntimeError(f"Réponse non-JSON ou JSON invalide: {exc}. Extrait: {snippet}") from exc

    # Minimal sanity checks to keep downstream robust
    if not isinstance(data, dict) or "recipe" not in data or not isinstance(data.get("recipe"), dict):
        raise RuntimeError(f"JSON inattendu (clé 'recipe' manquante): {data}")

    return data


def _call_openai_tts(text: str) -> Dict[str, str]:
    """Appel OpenAI Text-to-Speech.

    Retourne un dict avec:
      - audio_base64 (pour lecture côté client)
      - file_path (mp3 sauvegardé localement, utile en debug)

    Requis: OPENAI_API_KEY
    Optionnel:
      - OPENAI_TTS_MODEL (défaut: tts-1)
      - OPENAI_TTS_VOICE (défaut: alloy)
      - OPENAI_TTS_FORMAT (défaut: mp3)
      - TTS_OUTPUT_DIR (défaut: tts_outputs)
    """

    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "La librairie 'openai' n'est pas installée. Installe-la puis relance l'action server."
        ) from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY n'est pas défini. Configure la variable d'environnement et réessaie."
        )

    model = os.getenv("OPENAI_TTS_MODEL", "tts-1")
    voice = os.getenv("OPENAI_TTS_VOICE", "alloy")
    # WAV is easiest to play locally on Windows via `winsound`.
    audio_format = os.getenv("OPENAI_TTS_FORMAT", "wav")
    out_dir = Path(os.getenv("TTS_OUTPUT_DIR", "tts_outputs"))
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"tts_{uuid.uuid4().hex}.{audio_format}"
    file_path = out_dir / filename

    client = OpenAI(api_key=api_key)

    # OpenAI SDK returns a binary response helper for audio. Handle both common APIs.
    response = client.audio.speech.create(
        model=model,
        voice=voice,
        input=text,
        format=audio_format,
    )

    audio_bytes: Optional[bytes] = None
    if hasattr(response, "read"):
        audio_bytes = response.read()
    elif hasattr(response, "content"):
        audio_bytes = response.content  # type: ignore[assignment]
    elif hasattr(response, "stream_to_file"):
        response.stream_to_file(str(file_path))
        audio_bytes = file_path.read_bytes()
    else:
        raise RuntimeError("Réponse TTS OpenAI inattendue (format binaire non accessible).")

    if not audio_bytes:
        raise RuntimeError("Réponse OpenAI TTS vide.")

    file_path.write_bytes(audio_bytes)

    mime_type = "audio/mpeg" if audio_format.lower() in {"mp3", "mpeg"} else f"audio/{audio_format}"
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

    return {
        "text": text,
        "mime_type": mime_type,
        "audio_base64": audio_b64,
        "file_path": str(file_path),
        "model": model,
        "voice": voice,
    }


def _truthy_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _play_audio_local_async(file_path: str) -> None:
    # Fire-and-forget so we don't block the action server.
    thread = threading.Thread(target=_play_audio_local, args=(file_path,), daemon=True)
    thread.start()


def _play_audio_local(file_path: str) -> None:
    system = platform.system().lower()

    if system == "windows":
        # Built-in Windows playback (best with WAV).
        try:
            import winsound
        except Exception:
            return

        # If not WAV, Windows can fail; prefer setting OPENAI_TTS_FORMAT=wav.
        flags = winsound.SND_FILENAME
        if not _truthy_env("TTS_PLAY_AUDIO_SYNC", default=False):
            flags |= winsound.SND_ASYNC

        try:
            winsound.PlaySound(file_path, flags)
        except Exception:
            return

    # Minimal best-effort for other OS (optional)
    # else:
    #   no-op