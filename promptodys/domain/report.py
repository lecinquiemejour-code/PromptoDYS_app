"""Contenu du rapport de session, en Markdown.

Le rendu PDF (reportlab) relève de l'infrastructure : ce module ne fait qu'assembler le texte.
"""

from datetime import datetime

from promptodys.domain import ports


def _indented(text: str) -> str:
    """Chaque ligne précédée de quatre espaces (bloc de code Markdown)."""
    return "".join(f"    {line}\n" for line in text.split("\n"))


def build_report_markdown(
    original_note: str,
    step_logs: list[str],
    ai_stream: str,
    processed_note: str,
    correction_debrief: str,
    token_stats: ports.AITokenStats | None,
    model: str,
    thinking_level: str,
    generated_at: datetime,
) -> str:
    """Assemble le rapport complet de la session (métadonnées, note d'origine, logs, flux de l'IA,
    note traitée, débrief), en Markdown.

    model et thinking_level sont affichés tels quels, sauf thinking_level mis en forme (« LOW » → « Low »).
    """
    report = "# Rapport PromptoDYS - Session Complète\n\n"
    report += f"**Date de génération :** {generated_at.strftime('%d/%m/%Y à %H:%M:%S')}\n\n"

    # SECTION 1 : Métadonnées
    report += "## 📊 Métadonnées de la Session\n\n"
    if token_stats:
        report += f"- **Input tokens :** {token_stats.get('input', 'N/A')}\n"
        report += f"- **Output tokens :** {token_stats.get('output', 'N/A')}\n"
        report += f"- **Thinking tokens :** {token_stats.get('thinking', 'N/A')}\n"
        report += f"- **Total tokens :** {token_stats.get('total', 'N/A')}\n\n"
    report += "---\n\n"

    # SECTION 2 : Contenu original
    report += "## 📄 Contenu Original de l'Éditeur\n\n"
    report += "**CONTENU ORIGINAL :**\n\n"
    report += _indented(original_note or "(Aucun contenu)")
    report += "\n---\n\n"

    # SECTION 3 : Log des étapes de traitement
    report += "## 🔧 Log Complet du Traitement IA\n\n"
    report += "**ÉTAPES DE TRAITEMENT :**\n\n"
    report += "".join(f"    {log}\n" for log in step_logs)
    report += "\n---\n\n"

    # SECTION 4 : Flux complet de l'IA
    report += "## 🤖 Streaming Gemini Complet\n\n"
    report += "**THINKING + RÉPONSE EN TEMPS RÉEL :**\n\n"
    report += _indented(ai_stream or "(Aucun streaming capturé)")
    report += "\n---\n\n"

    # SECTION 5 : Contenu traité final
    report += "## ✅ Contenu Traité Final (Résultat)\n\n"
    report += processed_note or "(Aucun contenu traité)"
    report += "\n\n---\n\n"

    # SECTION 6 : Débrief de correction
    report += "## 📝 Débrief de la Correction par l'IA\n\n"
    report += correction_debrief or "(Aucun débrief disponible)"
    report += "\n\n---\n\n"

    # SECTION 7 : Pied de page
    report += "## 📋 Informations de Session\n\n"
    report += "- **Script :** PromptoDYS avec capture complète des logs\n"
    report += f"- **Modèle IA :** {model}\n"
    report += f"- **Thinking Level :** {thinking_level.capitalize()}\n"
    report += "- **Sauvegarde :** Automatique PDF uniquement\n\n"

    return report
