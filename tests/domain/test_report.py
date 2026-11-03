from datetime import datetime

from promptodys.domain.report import build_report_markdown


def _report(**overrides):
    """Rapport construit avec des valeurs par défaut, modifiables argument par argument."""
    args = {
        "original_note": "note brute",
        "step_logs": ["étape 1", "étape 2"],
        "ai_stream": "💭 réflexion\nréponse",
        "processed_note": "note corrigée",
        "correction_debrief": "3 fautes",
        "token_stats": {"input": 10, "output": 20, "thinking": 5, "total": 35},
        "model": "gemini-test",
        "thinking_level": "LOW",
        "generated_at": datetime(2026, 11, 2, 14, 30, 5),
    }
    args.update(overrides)
    return build_report_markdown(**args)


def test_report_contains_all_sections_in_order():
    """Les sept sections apparaissent, dans l'ordre."""
    report = _report()
    titles = [
        "## 📊 Métadonnées de la Session",
        "## 📄 Contenu Original de l'Éditeur",
        "## 🔧 Log Complet du Traitement IA",
        "## 🤖 Streaming Gemini Complet",
        "## ✅ Contenu Traité Final (Résultat)",
        "## 📝 Débrief de la Correction par l'IA",
        "## 📋 Informations de Session",
    ]
    positions = [report.index(title) for title in titles]
    assert positions == sorted(positions)


def test_report_uses_given_date_model_and_thinking_level():
    """La date, le modèle et le niveau de réflexion (mis en forme) sont ceux passés en paramètre."""
    report = _report()
    assert "**Date de génération :** 02/11/2026 à 14:30:05" in report
    assert "- **Modèle IA :** gemini-test" in report
    assert "- **Thinking Level :** Low" in report


def test_report_indents_original_note_logs_and_stream():
    """Note d'origine, logs et flux sont indentés de quatre espaces (blocs de code)."""
    report = _report(original_note="l1\nl2")
    assert "    l1\n    l2\n" in report
    assert "    étape 1\n    étape 2\n" in report
    assert "    💭 réflexion\n    réponse\n" in report


def test_report_token_stats():
    """Les jetons sont affichés, N/A pour une valeur manquante, rien sans statistiques."""
    report = _report(token_stats={"input": 10})
    assert "- **Input tokens :** 10" in report
    assert "- **Output tokens :** N/A" in report
    assert "tokens :**" not in _report(token_stats=None)


def test_report_placeholders_when_empty():
    """Des mentions remplacent les contenus vides."""
    report = _report(original_note="", ai_stream="", processed_note="", correction_debrief="")
    assert "(Aucun contenu)" in report
    assert "(Aucun streaming capturé)" in report
    assert "(Aucun contenu traité)" in report
    assert "(Aucun débrief disponible)" in report
