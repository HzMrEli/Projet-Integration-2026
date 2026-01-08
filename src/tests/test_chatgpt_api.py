from __future__ import annotations

import os
import random


def call_chatgpt_simple(prompt: str) -> str:
    """Minimal OpenAI call (no Rasa).

    Required env:
      - OPENAI_API_KEY

    Optional env:
      - OPENAI_MODEL (default: gpt-4o-mini)
    """

    try:
        from openai import OpenAI
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "La librairie 'openai' n'est pas installée. "
            "Installe-la puis relance: pip install openai"
        ) from exc

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY n'est pas défini. "
            "PowerShell (session): $env:OPENAI_API_KEY='sk-...'; python src/tests/test_chatgpt_api.py"
        )

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    client = OpenAI(api_key=api_key)
    try:
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Tu réponds de manière utile et concise."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.7,
        )
    except Exception as exc:
        raise RuntimeError(f"Erreur appel OpenAI: {exc}") from exc

    content = resp.choices[0].message.content
    return (content or "").strip()


def _random_prompt() -> str:
    proteins = ["poulet", "oeufs", "thon", "pois chiches", "tofu"]
    vegetables = ["carottes", "tomates", "courgettes", "poivrons", "épinards"]
    carbs = ["riz", "pâtes", "pommes de terre", "semoule", "quinoa"]
    contraintes = ["aucune", "végétarien", "sans gluten", "rapide", "léger"]
    difficulties = ["débutant", "intermédiaire"]
    max_minutes = [15, 20, 30, 45]
    persons = [1, 2, 3, 4]

    chosen_ingredients = [
        random.choice(proteins),
        random.choice(vegetables),
        random.choice(carbs),
        random.choice(["oignon", "ail", "citron", "crème", "yaourt", "fromage"]),
    ]
    random.shuffle(chosen_ingredients)

    prompt = (
        "Tu es un assistant de cuisine. Propose UNE recette en français. "
        "Donne: nom, ingrédients avec quantités, puis étapes numérotées courtes. "
        "Si des ingrédients manquent, propose des substitutions simples.\n\n"
        f"Ingrédients disponibles: {', '.join(chosen_ingredients)}\n"
        f"Contraintes: {random.choice(contraintes)}\n"
        f"Difficulté: {random.choice(difficulties)}\n"
        f"Temps max: {random.choice(max_minutes)} minutes\n"
        f"Nombre de personnes: {random.choice(persons)}\n"
    )
    return prompt


def main() -> int:
    prompt = _random_prompt()
    print("Prompt envoyé:\n" + prompt)
    print("\n--- Réponse ---\n")
    answer = call_chatgpt_simple(prompt)
    print(answer)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
