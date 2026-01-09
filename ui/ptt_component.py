from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional

import streamlit.components.v1 as components


_COMPONENT_DIR = Path(__file__).parent / "components" / "push_to_talk"

push_to_talk = components.declare_component(
    "push_to_talk",
    path=str(_COMPONENT_DIR),
)


def push_to_talk_audio(key: str = "ptt") -> Optional[Dict[str, Any]]:
    """Hold SPACE to record, release to send.

    Returns a dict like:
      {"audio_base64": "...", "mime_type": "audio/webm", "filename": "ptt.webm"}
    or None if no new audio.
    """

    value = push_to_talk(key=key, default=None)
    if isinstance(value, dict):
        return value
    return None
