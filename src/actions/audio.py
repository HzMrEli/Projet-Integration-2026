from __future__ import annotations

import os
import platform
import threading


def truthy_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def play_audio_local_async(file_path: str) -> None:
    thread = threading.Thread(target=play_audio_local, args=(file_path,), daemon=True)
    thread.start()


def play_audio_local(file_path: str) -> None:
    system = platform.system().lower()

    if system == "windows":
        try:
            import winsound
        except Exception as e:
            print(f"[AUDIO] winsound import error: {e}")
            return

        flags = winsound.SND_FILENAME
        if not truthy_env("TTS_PLAY_AUDIO_SYNC", default=False):
            flags |= winsound.SND_ASYNC

        try:
            print(f"[AUDIO] Trying to play: {file_path}")
            winsound.PlaySound(file_path, flags)
            print(f"[AUDIO] PlaySound call finished for: {file_path}")
        except Exception as e:
            print(f"[AUDIO] winsound.PlaySound error: {e}")
            return
