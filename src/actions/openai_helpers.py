from __future__ import annotations

import base64
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from openai import api_key
import openai


def call_openai_json(prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
    """Appel OpenAI qui retourne un dict JSON (robuste).

    - Utilise `responses.create(..., response_format=json_schema)` si dispo.
    - Sinon fallback sur `chat.completions.create(..., response_format=json_object)`.

    Requis: variable d'environnement OPENAI_API_KEY.
    Optionnel: OPENAI_MODEL (défaut: gpt-4o-mini), OPENAI_TIMEOUT_S (défaut: 60).
    """

    try:
        import openai
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "La librairie 'openai' n'est pas installée. Installe-la puis relance l'action server."
        ) from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY n'est pas défini. Configure la variable d'environnement et réessaie."
        )

    # openai==0.28.1 (legacy) uses ChatCompletion.
    # IMPORTANT: choose a model that exists for your account (ex: gpt-4o-mini, gpt-4o, gpt-3.5-turbo).
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    timeout_s = float(os.getenv("OPENAI_TIMEOUT_S", "60"))

    openai.api_key = api_key
    # Configure le timeout pour aiohttp (utilisé par openai==0.28.1)
    openai.request_timeout = timeout_s

    system = (
        "Tu es un assistant de cuisine. "
        "Tu dois produire une sortie JSON STRICTE conforme au schéma suivant. "
        "Ne mets jamais de texte hors JSON. "
        "Si une alternative n'existe pas, mets alternative=null. "
        "Si un ingrédient est critique, mets alternative=null.\n\n"
        "Schéma attendu :\n"
        '{"recipe": {"name": "nom_recette", "ingredients": [{"name": "nom_ingredient", "quantity": "quantité", "critical": true/false, "alternative": "alternative ou null"}], '
        '"instructions": ["étape 1", "étape 2"], "serving_suggestions": ["suggestion"], '
        '"preparation_time": "X minutes", "cooking_time": "X minutes", "total_time": "X minutes"}}\n\n'
        "Exemple concret :\n"
        '{"recipe": {"name": "crêpes", "ingredients": [{"name": "farine", "quantity": "250g", "critical": true, "alternative": null}, '
        '{"name": "oeufs", "quantity": "3", "critical": true, "alternative": null}, {"name": "lait", "quantity": "500ml", "critical": true, "alternative": null}, '
        '{"name": "beurre", "quantity": "50g", "critical": false, "alternative": "huile"}, {"name": "sucre", "quantity": "30g", "critical": false, "alternative": "miel"}, '
        '{"name": "sel", "quantity": "une pincée", "critical": false, "alternative": null}], '
        '"instructions": ["Dans un saladier, mélanger la farine et le sel.", "Faire un puits au centre et ajouter les oeufs.", '
        '"Incorporer progressivement le lait tout en fouettant pour éviter les grumeaux.", '
        '"Ajouter le beurre fondu et le sucre, puis mélanger jusqu\'à obtenir une pâte lisse.", "Laisser reposer la pâte pendant 30 minutes.", '
        '"Chauffer une poêle antiadhésive et y verser une louche de pâte.", "Cuire chaque crêpe environ 1 à 2 minutes de chaque côté jusqu\'à ce qu\'elle soit dorée.", '
        '"Répéter l\'opération jusqu\'à épuisement de la pâte."], '
        '"serving_suggestions": ["Servir avec du sucre, de la confiture, du chocolat fondu ou des fruits."], '
        '"preparation_time": "10 minutes", "cooking_time": "20 minutes", "total_time": "30 minutes"}}'
    )

    # openai==0.28.1 doesn't support `response_format`/`json_schema`.
    # We enforce strict JSON via instructions and parse defensively.
    json_only_instructions = (
        "\n\nIMPORTANT: Réponds UNIQUEMENT avec un objet JSON valide. "
        "Aucun texte avant/après. Pas de markdown. "
        "Respecte la structure attendue (clé racine 'recipe')."
    )

    text: Optional[str] = None
    resp = openai.ChatCompletion.create(
        model=model,
        messages=[
            {"role": "system", "content": system + json_only_instructions},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    try:
        text = resp["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"Réponse OpenAI inattendue: {resp}") from exc

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

    # openai==0.28.1 doesn't have the new client.audio.speech helper.
    # We use direct HTTP request instead.
    openai.api_key = api_key
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    
    data = {
        "model": os.getenv("OPENAI_TTS_MODEL", "tts-1"),
        "input": text,
        "voice": os.getenv("OPENAI_TTS_VOICE", "alloy"),
        "response_format": os.getenv("OPENAI_TTS_FORMAT", "wav"),
    }

    import requests
    response = requests.post(
        url,
        headers=headers,
        json=data,
        timeout=float(os.getenv("OPENAI_TIMEOUT_S", "60"))
    )
    
    if response.status_code != 200:
        raise RuntimeError(f"OpenAI TTS API Error: {response.status_code} - {response.text}")

    out_dir = Path(os.getenv("TTS_OUTPUT_DIR", "tts_outputs"))
    out_dir.mkdir(parents=True, exist_ok=True)
    
    audio_format = data["response_format"]
    filename = f"tts_{uuid.uuid4().hex}.{audio_format}"
    file_path = out_dir / filename

    file_path.write_bytes(response.content)
    
    with open(file_path, "rb") as f:
        audio_base64 = base64.b64encode(f.read()).decode("utf-8")

    return {
        "text": text,
        "file_path": str(file_path.absolute()),
        "audio_base64": audio_base64,
        "mime_type": f"audio/{audio_format}",
        "model": data["model"],
        "voice": data["voice"],
    }

    file_path.write_bytes(audio_bytes)

    mime_type = "audio/mpeg" if audio_format.lower(
    ) in {"mp3", "mpeg"} else f"audio/{audio_format}"
    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

    return {
        "text": text,
        "mime_type": mime_type,
        "audio_base64": audio_b64,
        "file_path": str(file_path),
        "model": model,
        "voice": voice,
    }
