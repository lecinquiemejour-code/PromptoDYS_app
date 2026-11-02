"""Règles sur la note : prompt envoyé à l'IA, extraction de la réponse, note d'origine."""

import logging
import re
from datetime import date

_logger = logging.getLogger(__name__)

NOTE_START = "<NOTE>"
NOTE_END = "</NOTE>"

# Marqueurs __BOLD_n__ du convertisseur Markdown de l'éditeur, parfois recopiés par Gemini
_BOLD_MARKER_PATTERN = re.compile(r"__BOLD_\d+__")

# Images Markdown de l'éditeur, ex. ![photo](./images/photo.png){width=300px id=...}, ou balises <img>
_IMAGE_MARKUP_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]*\)(\{[^}]*\})?|<img[^>]*>")

# Trois sauts de ligne ou plus : lignes vides en trop, par exemple laissées par les images retirées
_EXTRA_BLANK_LINES_PATTERN = re.compile(r"\n{3,}")

# Séparateur Markdown (---) en fin de texte, avec les blancs qui l'entourent
_TRAILING_SEPARATOR_PATTERN = re.compile(r"(\s*\n)?-{3,}\s*$")


def build_prompt(template: str, text: str, today: date) -> str:
    """Remplace [TEXTE] par la note de l'élève et [DATE] par la date du jour (JJ/MM/AAAA)."""
    return template.replace("[TEXTE]", text).replace("[DATE]", today.strftime("%d/%m/%Y"))


def replace_bold_markers(text: str) -> tuple[str, int]:
    """Remplace les marqueurs __BOLD_n__ par des séparateurs Markdown ---.
    Renvoie (texte, nombre de marqueurs remplacés)."""
    return _BOLD_MARKER_PATTERN.subn("---", text)


def has_note_tags(response: str) -> bool:
    """Vrai si la réponse contient les balises <NOTE> et </NOTE>."""
    return NOTE_START in response and NOTE_END in response


def extract_note_content(response: str) -> str:
    """Renvoie le contenu entre <NOTE> et </NOTE>, sans espaces autour.
    Sans les deux balises, renvoie la réponse entière. Les marqueurs __BOLD_n__ sont remplacés."""
    if not has_note_tags(response):
        _logger.warning("⚠️ ATTENTION: Balises <NOTE> absentes, utilisation complète")
        return replace_bold_markers(response)[0]

    start = response.find(NOTE_START) + len(NOTE_START)
    end = response.find(NOTE_END)
    content, bold_count = replace_bold_markers(response[start:end].strip())
    if bold_count > 0:
        _logger.info(f"🔄 NOTE: {bold_count} marqueurs __BOLD_n__ remplacés par des séparateurs ---")
    return content


def extract_correction_debrief(response: str) -> str:
    """Renvoie le débrief de correction, c'est-à-dire le texte qui suit </NOTE> (vide sans la balise)."""
    if NOTE_END not in response:
        return ""
    return response[response.find(NOTE_END) + len(NOTE_END) :].strip()


def append_original_note(processed_note: str, original_note: str) -> str:
    """Ajoute la note d'origine (sans les images) à la fin de la note corrigée.
    Générée côté Python plutôt que par Gemini : copie exacte et jetons de sortie économisés.
    Renvoie la note corrigée telle quelle si elle est vide ou si la note d'origine n'a que des images."""
    if not processed_note.strip():
        return processed_note
    original_without_images = _IMAGE_MARKUP_PATTERN.sub("", original_note)
    original_without_images = _EXTRA_BLANK_LINES_PATTERN.sub("\n\n", original_without_images).strip()
    if not original_without_images:
        return processed_note
    # Retirer un éventuel séparateur final pour ne pas le doubler
    processed_note = _TRAILING_SEPARATOR_PATTERN.sub("", processed_note.rstrip())
    _logger.info(f"📎 NOTE: Note d'origine ajoutée ({len(original_without_images)} caractères)")
    return (
        f"{processed_note}\n\n---\n\n"
        f'### <span style="color: #3399ff;">Note d\'origine</span>\n\n'
        f"{original_without_images}\n"
    )
