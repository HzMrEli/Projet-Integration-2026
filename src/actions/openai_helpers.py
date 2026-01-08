from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional


def call_openai_json(prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
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
        raise RuntimeError(
            f"Réponse non-JSON ou JSON invalide: {exc}. Extrait: {snippet}"
        ) from exc

    if not isinstance(data, dict) or "recipe" not in data or not isinstance(data.get("recipe"), dict):
        raise RuntimeError(f"JSON inattendu (clé 'recipe' manquante): {data}")

    return data


def call_openai_tts(text: str) -> Dict[str, str]:
    """Appel OpenAI Text-to-Speech.

    Retourne un dict avec:
      - audio_base64 (pour lecture côté client)
      - file_path (audio sauvegardé localement, utile en debug)

    Requis: OPENAI_API_KEY
    Optionnel:
      - OPENAI_TTS_MODEL (défaut: tts-1)
      - OPENAI_TTS_VOICE (défaut: alloy)
      - OPENAI_TTS_FORMAT (défaut: wav)
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
    audio_format = os.getenv("OPENAI_TTS_FORMAT", "wav")

    out_dir = Path(os.getenv("TTS_OUTPUT_DIR", "tts_outputs"))
    out_dir.mkdir(parents=True, exist_ok=True)

    filename = f"tts_{uuid.uuid4().hex}.{audio_format}"
    file_path = out_dir / filename

    client = OpenAI(api_key=api_key)

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
