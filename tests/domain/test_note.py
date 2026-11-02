import logging
from datetime import date

from promptodys.domain.note import (
    append_original_note,
    build_prompt,
    extract_correction_debrief,
    extract_note_content,
    has_note_tags,
    replace_bold_markers,
)

# --- build_prompt ---


def test_build_prompt_substitutes_text_and_date():
    """[TEXTE] reçoit la note, [DATE] la date du jour au format JJ/MM/AAAA."""
    template = "Date : [DATE]\nNote :\n[TEXTE]"
    assert build_prompt(template, "ma note", date(2026, 3, 7)) == "Date : 07/03/2026\nNote :\nma note"


# --- replace_bold_markers ---


def test_replace_bold_markers_counts_replacements():
    """Chaque marqueur __BOLD_n__ devient ---, et le nombre de remplacements est renvoyé."""
    assert replace_bold_markers("a __BOLD_1__ b __BOLD_42__") == ("a --- b ---", 2)


def test_replace_bold_markers_without_marker():
    """Sans marqueur, le texte est inchangé et le compte est nul."""
    assert replace_bold_markers("__BOLD__ texte") == ("__BOLD__ texte", 0)


# --- has_note_tags ---


def test_has_note_tags_needs_both_tags():
    """Les deux balises sont nécessaires."""
    assert has_note_tags("<NOTE>x</NOTE>")
    assert not has_note_tags("<NOTE>x")
    assert not has_note_tags("x</NOTE>")


# --- extract_note_content ---


def test_extract_note_content_between_tags():
    """Seul le contenu entre <NOTE> et </NOTE> est gardé, sans espaces autour."""
    response = "Préambule\n<NOTE>\n  # Ma note\n\nTexte  \n</NOTE>\nDébrief"
    assert extract_note_content(response) == "# Ma note\n\nTexte"


def test_extract_note_content_replaces_bold_markers():
    """Les marqueurs __BOLD_n__ deviennent des séparateurs Markdown."""
    response = "<NOTE>Début\n__BOLD_1__\nMilieu\n__BOLD_12__\nFin</NOTE>"
    assert extract_note_content(response) == "Début\n---\nMilieu\n---\nFin"


def test_extract_note_content_without_tags_returns_everything():
    """Sans balises, la réponse entière est utilisée, marqueurs remplacés."""
    response = "Texte sans balises\n__BOLD_3__\nSuite"
    assert extract_note_content(response) == "Texte sans balises\n---\nSuite"


def test_extract_note_content_missing_closing_tag():
    """Une balise ouvrante seule ne suffit pas : la réponse entière est renvoyée."""
    response = "<NOTE>Note tronquée"
    assert extract_note_content(response) == response


# --- extract_correction_debrief ---


def test_extract_debrief_after_tag():
    """Le débrief est le texte qui suit </NOTE>."""
    response = "<NOTE>Note</NOTE>\n\n  Corrections : 3 fautes  \n"
    assert extract_correction_debrief(response) == "Corrections : 3 fautes"


def test_extract_debrief_without_tag():
    """Sans </NOTE>, pas de débrief."""
    assert extract_correction_debrief("Réponse sans balises") == ""


def test_extract_debrief_empty_after_tag():
    """Rien après </NOTE> : débrief vide."""
    assert extract_correction_debrief("<NOTE>Note</NOTE>\n  ") == ""


# --- append_original_note ---


def test_append_original_note_adds_block():
    """La note d'origine est ajoutée après un séparateur et un titre."""
    result = append_original_note("Note corrigée", "Note d'origine brute")
    assert result == (
        "Note corrigée\n\n---\n\n"
        "### <span style=\"color: #3399ff;\">Note d'origine</span>\n\n"
        "Note d'origine brute\n"
    )  # fmt: skip


def test_append_original_note_removes_images():
    """Images Markdown de l'éditeur et balises <img> sont retirées de la note d'origine."""
    original = (
        "Avant\n\n"
        "![photo](./images/photo.png){width=300px id=abc}\n\n"
        '<img src="./images/schema.png" />\n\n'
        "Après"
    )  # fmt: skip
    result = append_original_note("Corrigée", original)
    assert "images/" not in result
    assert "<img" not in result
    # Les lignes vides laissées par les images sont réduites à une seule
    assert "Avant\n\nAprès" in result


def test_append_original_note_does_not_double_separator():
    """Un séparateur en fin de note corrigée n'est pas doublé."""
    result = append_original_note("Note corrigée\n\n---\n", "Origine")
    assert result.count("---") == 1


def test_append_original_note_empty_processed_note():
    """Une note corrigée vide est renvoyée telle quelle."""
    assert append_original_note("  \n", "Origine") == "  \n"


def test_append_original_note_original_only_images():
    """Une note d'origine faite seulement d'images n'ajoute rien."""
    original = '![a](./images/a.png)\n\n<img src="b.png">'
    assert append_original_note("Corrigée", original) == "Corrigée"


# --- Logs ---


def test_extract_note_content_logs_bold_markers_in_note_only(caplog):
    """Le nombre de marqueurs remplacés est journalisé, compté dans la note seule (pas dans le débrief)."""
    caplog.set_level(logging.INFO, logger="promptodys")
    extract_note_content("<NOTE>a __BOLD_1__ b</NOTE> débrief __BOLD_2__")
    assert "🔄 NOTE: 1 marqueurs __BOLD_n__ remplacés par des séparateurs ---" in caplog.messages


def test_extract_note_content_logs_missing_tags(caplog):
    """L'absence de balises est signalée en avertissement."""
    caplog.set_level(logging.INFO, logger="promptodys")
    extract_note_content("Texte sans balises")
    assert [(r.levelno, r.getMessage()) for r in caplog.records] == [
        (logging.WARNING, "⚠️ ATTENTION: Balises <NOTE> absentes, utilisation complète")
    ]


def test_append_original_note_logs_its_length(caplog):
    """L'ajout de la note d'origine est journalisé avec sa taille, images retirées."""
    caplog.set_level(logging.INFO, logger="promptodys")
    append_original_note("Corrigée", "Origine\n\n![a](./images/a.png)")
    assert "📎 NOTE: Note d'origine ajoutée (7 caractères)" in caplog.messages
