from __future__ import annotations

from typing import Any, Dict, List, Text

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet
import re
import unicodedata


def _normalize(s: str) -> str:
    s = s.lower().strip()
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s


def _split_ingredients(text: str) -> List[str]:
    parts = re.split(r',|;|/|\band\b|\bet\b|\s&\s|\s-\s',
                     text, flags=re.IGNORECASE)
    items: List[str] = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # remove common leading phrases
        p = re.sub(r'^(j\'ai|jai|j ai|il y a|on a|j\'ai des|j ai des)\s+',
                   '', p, flags=re.IGNORECASE)
        # remove common verbs like "j'ai" left after split
        p = re.sub(r"^des\s+", '', p, flags=re.IGNORECASE)
        items.append(_normalize(p))

    # dedupe preserving order
    seen = set()
    dedup: List[str] = []
    for it in items:
        if it and it not in seen:
            dedup.append(it)
            seen.add(it)
    return dedup


class ActionCollectIngredients(Action):
    def name(self) -> Text:
        return "action_collect_ingredients"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        text = tracker.latest_message.get('text') or ''

        # extract ingredient entities if present
        entities = [e.get('value') for e in tracker.latest_message.get(
            'entities', []) if e.get('entity') == 'ingredient']
        normalized_entities = [_normalize(e) for e in entities if e]

        tokens: List[str]
        if normalized_entities:
            tokens = normalized_entities
        else:
            tokens = _split_ingredients(text)

        current = tracker.get_slot('ingredients') or []
        if not isinstance(current, list):
            current = [current] if current else []

        merged = current[:]
        for t in tokens:
            if t and t not in merged:
                merged.append(t)

        dispatcher.utter_message(
            response="utter_confirm_ingredients", ingredients=', '.join(merged))

        return [SlotSet('ingredients', merged)]
