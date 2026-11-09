#!/usr/bin/env python3
"""PromptoDYS : éditeur Markdown avec correction de la prise de note par l'IA Gemini.

Point d'entrée historique, gardé car PromptoDYS.spec, le workflow de release et la documentation le citent.
Le code est dans le paquet promptodys/ (voir doc/ARCHITECTURE.md) ; main() est dans promptodys/app.py.

Usage :
    uv sync --locked
    uv run python askGeminiPrompto.py    (ou : uv run python -m promptodys)
"""

from promptodys.app import main

if __name__ == "__main__":
    main()
