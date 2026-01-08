from __future__ import annotations

from typing import Any, Dict


RECIPE_SCHEMA: Dict[str, Any] = {
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
