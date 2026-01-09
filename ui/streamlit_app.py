from __future__ import annotations

import hashlib
import io
import os
import base64
from typing import Any, Dict, List, Optional

import requests
import streamlit as st

from ui.ptt_component import push_to_talk_audio


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


def _post_rasa_message(rasa_url: str, sender_id: str, message: str, timeout_s: float = 20.0) -> List[Dict[str, Any]]:
    url = f"{rasa_url.rstrip('/')}/webhooks/rest/webhook"
    resp = requests.post(
        url,
        json={"sender": sender_id, "message": message},
        timeout=timeout_s,
    )
    resp.raise_for_status()

    data = resp.json()
    if isinstance(data, list):
        return data
    return []


def _get_rasa_tracker_slots(rasa_url: str, sender_id: str, timeout_s: float = 10.0) -> Dict[str, Any]:
    url = f"{rasa_url.rstrip('/')}/conversations/{sender_id}/tracker"
    resp = requests.get(url, timeout=timeout_s)
    resp.raise_for_status()
    tracker = resp.json()
    slots = tracker.get("slots")
    return slots if isinstance(slots, dict) else {}


def _render_bot_message(msg: Dict[str, Any]) -> None:
    text = msg.get("text")
    custom = msg.get("custom")  # json_message from Rasa becomes "custom" in REST channel
    image = msg.get("image")

    if isinstance(text, str) and text.strip():
        st.markdown(text)

    if isinstance(image, str) and image.strip():
        st.image(image)

    if custom is not None:
        with st.expander("Données (custom/json_message)", expanded=False):
            st.json(custom)


def _transcribe_with_openai(audio_bytes: bytes, filename: str, mime_type: str) -> str:
    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "La librairie 'openai' n'est pas installée. Installe-la puis relance l'UI."
        ) from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY n'est pas défini.")

    model = os.getenv("OPENAI_STT_MODEL", "whisper-1")
    client = OpenAI(api_key=api_key)

    # OpenAI expects a file-like object.
    file_obj = io.BytesIO(audio_bytes)
    file_obj.name = filename  # type: ignore[attr-defined]

    resp = client.audio.transcriptions.create(
        model=model,
        file=file_obj,
    )

    text = getattr(resp, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Transcription STT vide.")
    return text.strip()


def main() -> None:
    st.set_page_config(page_title="Rasa Chat UI", layout="centered")
    st.title("Conversation Rasa (Streamlit)")

    rasa_url = st.sidebar.text_input("Rasa URL", value=_env("RASA_URL", "http://localhost:5005"))
    sender_id = st.sidebar.text_input("Conversation ID", value=_env("RASA_SENDER_ID", "streamlit_user"))

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "last_slots" not in st.session_state:
        st.session_state["last_slots"] = {}
    if "last_audio_hash" not in st.session_state:
        st.session_state["last_audio_hash"] = None

    # Display technical slots (useful for your UI refresh / TTS markers)
    slots = st.session_state.get("last_slots") or {}
    ui_event = slots.get("ui_event")
    tts_last_file = slots.get("tts_last_file")
    with st.sidebar:
        st.caption("Slots techniques (tracker)")
        if ui_event is not None:
            st.json({"ui_event": ui_event})
        if isinstance(tts_last_file, str) and tts_last_file:
            st.code(tts_last_file)

    # Voice-only input with push-to-talk (hold SPACE).
    ptt = push_to_talk_audio(key="ptt")
    if ptt is None:
        return

    for m in st.session_state["messages"]:
        role = m.get("role", "assistant")
        content = m.get("content", "")
        with st.chat_message(role):
            st.markdown(content)

    audio_b64 = ptt.get("audio_base64")
    filename = str(ptt.get("filename") or "ptt.webm")
    mime_type = str(ptt.get("mime_type") or "audio/webm")

    if not isinstance(audio_b64, str) or not audio_b64:
        return

    try:
        audio_bytes = base64.b64decode(audio_b64)
    except Exception:
        return

    audio_hash = hashlib.sha256(audio_bytes).hexdigest()
    if st.session_state.get("last_audio_hash") == audio_hash:
        return
    st.session_state["last_audio_hash"] = audio_hash

    with st.chat_message("user"):
        try:
            with st.spinner("Transcription…"):
                user_text = _transcribe_with_openai(audio_bytes, filename=filename, mime_type=mime_type)
        except Exception as exc:
            st.error(f"Erreur STT: {exc}")
            return

        st.markdown(user_text)
        st.session_state["messages"].append({"role": "user", "content": user_text})

    with st.chat_message("assistant"):
        try:
            responses = _post_rasa_message(rasa_url=rasa_url, sender_id=sender_id, message=user_text)
        except requests.RequestException as exc:
            st.error(f"Erreur d'appel Rasa: {exc}")
            return

        # If the bot returned no messages (e.g., action only sets slots), we still refresh slots.
        if not responses:
            st.caption("(aucun message bot) — slots mis à jour")

        rendered_text_parts: List[str] = []
        for msg in responses:
            # Render rich fields and also build a plain text summary for chat history.
            _render_bot_message(msg)

            if isinstance(msg.get("text"), str) and msg["text"].strip():
                rendered_text_parts.append(msg["text"].strip())
            elif msg.get("custom") is not None:
                rendered_text_parts.append("[custom/json_message]")

        # Update tracker slots (for ui_event / tts_last_file)
        try:
            slots = _get_rasa_tracker_slots(rasa_url=rasa_url, sender_id=sender_id)
            st.session_state["last_slots"] = slots
        except requests.RequestException:
            pass

    # Store bot message as a compact text in history
    bot_summary = "\n\n".join(rendered_text_parts) if rendered_text_parts else "(aucun message)"
    st.session_state["messages"].append({"role": "assistant", "content": bot_summary})


if __name__ == "__main__":
    main()
