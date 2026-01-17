from __future__ import annotations

from contextlib import contextmanager
import hashlib
import io
import os
import base64
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import requests
import streamlit as st

from ptt_component import push_to_talk_audio


@contextmanager
def _chat_message(role: str):
    chat_message = getattr(st, "chat_message", None)
    if callable(chat_message):
        with cast(Any, chat_message)(role):
            yield
    else:
        with st.container():
            st.markdown(f"**{role}**")
            yield


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


def _post_rasa_message(rasa_url: str, sender_id: str, message: str, timeout_s: float = 60.0) -> List[Dict[str, Any]]:
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


def _reset_rasa_conversation(rasa_url: str, sender_id: str, timeout_s: float = 10.0) -> None:
    """Reset conversation côté Rasa Core.

    Essaie d'abord DELETE /tracker (si l'API le supporte), sinon fallback via un event 'restart'.
    """

    base = rasa_url.rstrip("/")

    # 1) Delete tracker (best effort)
    delete_url = f"{base}/conversations/{sender_id}/tracker"
    try:
        resp = requests.delete(delete_url, timeout=timeout_s)
        if 200 <= resp.status_code < 300:
            return
    except requests.RequestException:
        pass

    # 2) Fallback: inject restart event
    events_url = f"{base}/conversations/{sender_id}/tracker/events"
    for event_payload in (
        {"event": "restart"},
        # Dans certaines config, les slots/form peuvent rester dans un état inattendu.
        # Ce reset est safe et réduit fortement les conversations "bloquées".
        {"event": "reset_slots"},
    ):
        try:
            resp = requests.post(events_url, json=event_payload, timeout=timeout_s)
            if not (200 <= resp.status_code < 300):
                # Si l'endpoint existe mais refuse l'event, inutile d'insister.
                return
        except requests.RequestException:
            return


def _render_bot_message(msg: Dict[str, Any]) -> None:
    text = msg.get("text")
    # json_message from Rasa becomes "custom" in REST channel
    custom = msg.get("custom")
    image = msg.get("image")

    if isinstance(text, str) and text.strip():
        st.markdown(text)

    if isinstance(image, str) and image.strip():
        st.image(image)

    if custom is not None:
        # Auto-play TTS if available
        if isinstance(custom, dict) and "tts" in custom:
            tts_data = custom["tts"]
            audio_b64 = tts_data.get("audio_base64")
            if audio_b64:
                try:
                    mime_type = tts_data.get("mime_type", "audio/wav")
                    # Hack for autoplay on older Streamlit versions (<1.23.0)
                    audio_html = f"""
                        <audio controls autoplay style="width: 100%;">
                        <source src="data:{mime_type};base64,{audio_b64}" type="{mime_type}">
                        Your browser does not support the audio element.
                        </audio>
                    """
                    st.markdown(audio_html, unsafe_allow_html=True)
                except Exception:
                    pass

        with st.expander("Données (custom/json_message)", expanded=False):
            st.json(custom)


def _guess_audio_mime_type(path: Path) -> str:
    """Devine le mime type audio à partir de l'extension de fichier."""
    suffix = path.suffix.lower().lstrip(".")
    if suffix in {"mp3", "mpeg"}:
        return "audio/mpeg"
    if suffix == "wav":
        return "audio/wav"
    if suffix == "ogg":
        return "audio/ogg"
    if suffix == "webm":
        return "audio/webm"
    return "audio/wav"


def _render_local_audio_file(path: Path, autoplay: bool) -> None:
    """Affiche un lecteur audio Streamlit pour un fichier local."""
    try:
        audio_bytes = path.read_bytes()
    except Exception:
        return

    audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
    mime_type = _guess_audio_mime_type(path)
    autoplay_attr = "autoplay" if autoplay else ""

    # Generate stable ID based on path to prevent re-mounting on reruns
    element_id = f"audio_{hashlib.md5(str(path).encode()).hexdigest()}"

    # JavaScript fallback to force play if attribute fails (browser policy)
    js_code = ""
    if autoplay:
        js_code = f"""
<script>
    (function() {{
        var audio = document.getElementById("{element_id}");
        if (audio) {{
            audio.play().catch(function(e) {{ 
                console.warn("Autoplay blocked/failed:", e); 
            }});
        }}
    }})();
</script>
"""

    audio_html = f"""
        <audio id="{element_id}" controls {autoplay_attr} style="width: 100%;">
        <source src="data:{mime_type};base64,{audio_b64}" type="{mime_type}">
        Your browser does not support the audio element.
        </audio>
        {js_code}
    """
    st.markdown(audio_html, unsafe_allow_html=True)


def _transcribe_with_openai(audio_bytes: bytes, filename: str, mime_type: str) -> str:
    try:
        import openai
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "La librairie 'openai' n'est pas installée. Installe-la puis relance l'UI."
        ) from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY n'est pas défini.")

    model = os.getenv("OPENAI_STT_MODEL", "whisper-1")
    language = os.getenv("OPENAI_STT_LANGUAGE", "fr")

    # Support both SDKs:
    # - openai==0.28.x: openai.Audio.transcribe(...)
    # - openai>=1.x: client = openai.OpenAI(...); client.audio.transcriptions.create(...)
    openai.api_key = api_key

    # OpenAI expects a file-like object.
    file_obj = io.BytesIO(audio_bytes)
    file_obj.name = filename  # type: ignore[attr-defined]

    if hasattr(openai, "OpenAI"):
        OpenAIClient = cast(Any, getattr(openai, "OpenAI"))
        client = OpenAIClient(api_key=api_key)
        resp = client.audio.transcriptions.create(model=model, file=file_obj, language=language)
        text = getattr(resp, "text", None)
    else:
        # openai==0.28.x returns a dict-like object with a "text" field.
        try:
            resp = openai.Audio.transcribe(model=model, file=file_obj, language=language)
        except TypeError:
            resp = openai.Audio.transcribe(model, file_obj, language=language)

        if isinstance(resp, dict):
            text = resp.get("text")
        else:
            text = getattr(resp, "text", None)
    if not isinstance(text, str) or not text.strip():
        raise RuntimeError("Transcription STT vide.")
    return text.strip()


def main() -> None:
    st.set_page_config(page_title="Rasa Chat UI", layout="centered")
    st.title("Conversation Rasa (Streamlit)")

    # Persist settings across reruns without fighting Streamlit's widget state.
    if "active_rasa_url" not in st.session_state:
        st.session_state["active_rasa_url"] = _env("RASA_URL", "http://localhost:5005")
    if "active_sender_id" not in st.session_state:
        st.session_state["active_sender_id"] = _env("RASA_SENDER_ID", "streamlit_user")
    if "settings_nonce" not in st.session_state:
        st.session_state["settings_nonce"] = 0
    if "ptt_nonce" not in st.session_state:
        st.session_state["ptt_nonce"] = 0

    if "messages" not in st.session_state:
        st.session_state["messages"] = []
    if "last_slots" not in st.session_state:
        st.session_state["last_slots"] = {}
    if "last_audio_hash" not in st.session_state:
        st.session_state["last_audio_hash"] = None
    if "welcome_render_count" not in st.session_state:
        st.session_state["welcome_render_count"] = 0

    # Message de bienvenue (UI) au lancement.
    # On le ré-affiche aussi après un Reset (messages vidés).
    if not st.session_state["messages"]:
        repo_root = Path(__file__).resolve().parents[1]
        welcome_wav = repo_root / "ui" / "welcome.wav"
        st.session_state["messages"].append(
            {
                "role": "assistant",
                "content": (
                    "Bonjour ! Je suis votre assistant culinaire.\n\n"
                    "Je peux proposer des recettes complètes ou étape par étape à partir de vos ingrédients, ou à partir d'un nom de recette.\n"
                    "Dans la barre latérale, activer votre micro et maintenez ESPACE pour parler (push-to-talk)."
                ),
                "audio_path": str(welcome_wav) if welcome_wav.exists() else None,
            }
        )

    # Display technical slots (useful for your UI refresh / TTS markers)
    slots = st.session_state.get("last_slots") or {}
    ui_event = slots.get("ui_event")
    tts_last_file = slots.get("tts_last_file")
    with st.sidebar:
        nonce = int(st.session_state.get("settings_nonce", 0))

        if st.button("Reset", type="primary"):
            # Reset côté Rasa Core pour éviter de garder un tracker/form bloqué.
            try:
                _reset_rasa_conversation(
                    rasa_url=str(st.session_state.get("active_rasa_url") or _env("RASA_URL", "http://localhost:5005")),
                    sender_id=str(st.session_state.get("active_sender_id") or _env("RASA_SENDER_ID", "streamlit_user")),
                )
            except Exception:
                # Best-effort: si Rasa est down, on reset quand même l'UI.
                pass

            st.session_state["messages"] = []
            st.session_state["last_slots"] = {}
            st.session_state["last_audio_hash"] = None
            st.session_state["welcome_render_count"] = 0
            st.session_state["ptt_nonce"] = int(st.session_state.get("ptt_nonce", 0)) + 1
            # New conversation to reset server-side context as well.
            st.session_state["active_sender_id"] = f"streamlit_{uuid.uuid4().hex[:8]}"

            # Force la recréation des widgets de settings pour éviter que le front réinjecte
            # l'ancien sender_id/rasa_url après reset.
            st.session_state["settings_nonce"] = int(st.session_state.get("settings_nonce", 0)) + 1

            rerun = getattr(st, "rerun", None)
            if callable(rerun):
                rerun()
            else:
                st.experimental_rerun()

        rasa_url = st.text_input(
            "Rasa URL",
            value=str(st.session_state.get("active_rasa_url", "http://localhost:5005")),
            key=f"rasa_url_input_{nonce}",
        )
        sender_id = st.text_input(
            "Conversation ID",
            value=str(st.session_state.get("active_sender_id", "streamlit_user")),
            key=f"sender_id_input_{nonce}",
        )

        # Valeurs réellement utilisées pour contacter Rasa.
        st.session_state["active_rasa_url"] = rasa_url
        st.session_state["active_sender_id"] = sender_id

        st.caption("Slots techniques (tracker)")
        if ui_event is not None:
            st.json({"ui_event": ui_event})
        if isinstance(tts_last_file, str) and tts_last_file:
            st.code(tts_last_file)

        st.markdown("---")
        st.caption("Push-to-talk")
        # Le composant est rendu dans la sidebar, mais on traite l'audio plus bas.
        ptt = push_to_talk_audio(key=f"ptt_sidebar_{st.session_state['ptt_nonce']}")

    for m in st.session_state["messages"]:
        role = m.get("role", "assistant")
        content = m.get("content", "")
        audio_path = m.get("audio_path")
        with _chat_message(role):
            st.markdown(content)
            if isinstance(audio_path, str) and audio_path.strip():
                path = Path(audio_path)
                if path.exists():
                    # Autoplay logic:
                    # 1. Stop autoplay if user has sent messages (len > 1).
                    # 2. Otherwise/Initially, keep autoplay ON for a few renders (threshold=5)
                    #    to survive initial Streamlit reruns/flicker.
                    if len(st.session_state["messages"]) > 1:
                        autoplay = False
                    else:
                        cnt = st.session_state.get("welcome_render_count", 0)
                        autoplay = (cnt < 5)
                        st.session_state["welcome_render_count"] = cnt + 1
                    
                    _render_local_audio_file(path, autoplay=autoplay)

    if not isinstance(ptt, dict):
        # Aucun audio reçu (composant pas encore utilisé / pas de permission / rerun)
        return

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

    with _chat_message("user"):
        try:
            with st.spinner("Transcription…"):
                user_text = _transcribe_with_openai(
                    audio_bytes, filename=filename, mime_type=mime_type)
        except Exception as exc:
            st.error(f"Erreur STT: {exc}")
            return

        st.markdown(user_text)
        st.session_state["messages"].append(
            {"role": "user", "content": user_text})

    with _chat_message("assistant"):
        try:
            responses = _post_rasa_message(
                rasa_url=rasa_url, sender_id=sender_id, message=user_text)
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
            slots = _get_rasa_tracker_slots(
                rasa_url=rasa_url, sender_id=sender_id)
            st.session_state["last_slots"] = slots
        except requests.RequestException:
            pass
    

    # Store bot message as a compact text in history
    bot_summary = "\n\n".join(
        rendered_text_parts) if rendered_text_parts else "(aucun message)"
    st.session_state["messages"].append(
        {"role": "assistant", "content": bot_summary})


if __name__ == "__main__":
    main()
