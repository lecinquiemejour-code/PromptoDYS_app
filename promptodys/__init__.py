"""PromptoDYS, découpé en trois couches (voir doc/RECOMMANDATIONS.md, priorité 3).

- domain : règles pures, cas d'usage et ports (Protocol), sans Tk, Eel, Gemini ni reportlab
- infrastructure : adaptateurs vers Gemini, Eel, le disque et le PDF
- presentation : panneau de contrôle Tkinter

Règle de dépendance, vérifiée par import-linter : presentation → domain ← infrastructure.
"""
