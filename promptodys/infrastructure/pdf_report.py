"""Rapport PDF de la session, généré avec ReportLab.

Le contenu est assemblé en Markdown par le domaine (report.build_report_markdown), puis reparsé ici
ligne à ligne pour obtenir les éléments ReportLab. Ce reparsage est provisoire : R8 prévoit de
construire les éléments directement depuis les données.
"""

import logging
import os
import re
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer

from promptodys.domain import note, ports, report
from promptodys.infrastructure import config

_logger = logging.getLogger(__name__)


def clean_html_tags(text: str) -> str:
    """Supprime les balises HTML problématiques pour reportlab"""
    # Remplacer les marqueurs __BOLD_n__ par des séparateurs horizontaux MD
    text, bold_count = note.replace_bold_markers(text)
    if bold_count > 0:
        _logger.info(f"🔄 NETTOYAGE: {bold_count} marqueurs __BOLD_n__ remplacés par des séparateurs ---")

    # Supprimer les balises <span> avec styles
    text = re.sub(r"<span[^>]*>", "", text)
    text = re.sub(r"</span>", "", text)

    # Supprimer seulement les émojis problématiques pour reportlab
    text = re.sub(r"[🎉🎯🔧📊📝📄✅❌⚙️🚀🔍✏️🧠🔢💾🎮📋💡🤖📖🔗🪟📁⏳🔄💭]", "", text)

    # Nettoyer les caractères spéciaux
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Remettre les balises autorisées
    text = text.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
    text = text.replace("&lt;i&gt;", "<i>").replace("&lt;/i&gt;", "</i>")
    text = text.replace("&lt;u&gt;", "<u>").replace("&lt;/u&gt;", "</u>")

    return text


def markdown_to_flowables(markdown: str) -> list[Flowable]:
    """Convertit le contenu Markdown en paragraphes reportlab"""

    # Styles reportlab
    styles = getSampleStyleSheet()

    # Styles personnalisés
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Title"],
        fontSize=16,
        textColor=colors.darkblue,
        spaceAfter=15,
        alignment=1,  # Centré
    )

    heading1_style = ParagraphStyle(
        "CustomHeading1",
        parent=styles["Heading1"],
        fontSize=12,
        textColor=colors.darkblue,
        spaceBefore=12,
        spaceAfter=8,
    )

    heading2_style = ParagraphStyle(
        "CustomHeading2",
        parent=styles["Heading2"],
        fontSize=10,
        textColor=colors.darkslategray,
        spaceBefore=10,
        spaceAfter=6,
    )

    normal_style = ParagraphStyle(
        "CustomNormal",
        parent=styles["Normal"],
        fontSize=9,  # Plus gros pour meilleure lisibilité
        spaceBefore=6,
        spaceAfter=6,
        leftIndent=0,
        rightIndent=0,
    )

    code_style = ParagraphStyle(
        "CustomCode",
        parent=normal_style,
        fontSize=9,  # Plus gros pour meilleure lisibilité
        fontName="Helvetica",  # Police normale au lieu de Courier
        backgroundColor=colors.lightblue,  # Couleur plus visible
        borderWidth=2,
        borderColor=colors.darkblue,
        leftIndent=15,
        rightIndent=15,
        spaceBefore=8,
        spaceAfter=8,
        borderPadding=10,  # Plus d'espace autour du texte
    )

    # Parsing simple du Markdown
    flowables: list[Flowable] = []
    in_code_block = False

    for original_line in markdown.split("\n"):
        line = original_line.strip()

        if not line and not in_code_block:
            flowables.append(Spacer(1, 4))
            continue

        # Gestion des blocs de code (```)
        if line.startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            # Dans un bloc de code, garder le formatage original
            text_clean = clean_html_tags(original_line.rstrip())
            if text_clean.strip():  # Éviter les lignes complètement vides
                flowables.append(Paragraph(text_clean, code_style))
            continue

        # Nettoyer les balises HTML pour PDF
        line_clean = clean_html_tags(line)

        # Titre principal (# )
        if line_clean.startswith("# "):
            flowables.append(Paragraph(line_clean[2:].strip(), title_style))

        # Sous-titre niveau 1 (## )
        elif line_clean.startswith("## "):
            flowables.append(Paragraph(line_clean[3:].strip(), heading1_style))

        # Sous-titre niveau 2 (### )
        elif line_clean.startswith("### "):
            flowables.append(Paragraph(line_clean[4:].strip(), heading2_style))

        # Ligne de séparation (---)
        elif line_clean.startswith("---"):
            flowables.append(Spacer(1, 8))

        # Liste à puces (- ou *)
        elif line_clean.startswith("- ") or line_clean.startswith("* "):
            flowables.append(Paragraph(f"• {line_clean[2:].strip()}", normal_style))

        # Texte normal
        else:
            # Gérer le gras inline (**texte**)
            line_final = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", line_clean)

            # Gérer l'italique inline (*texte*)
            line_final = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", line_final)

            if line_final.strip():  # Éviter les paragraphes vides
                flowables.append(Paragraph(line_final, normal_style))

    return flowables


def generate_pdf(markdown: str, pdf_path: str) -> str | None:
    """Génère le PDF à partir du Markdown. Renvoie son chemin, None en cas d'erreur"""
    try:
        _logger.info("📁 ÉTAPE: Génération PDF avec reportlab...")

        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=A4,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch,
        )
        doc.build(markdown_to_flowables(markdown))

        _logger.info(f"✅ SUCCÈS: Fichier .pdf créé → {pdf_path}")
        return pdf_path

    except Exception as e:
        _logger.info(f"❌ ÉCHEC: Erreur génération PDF → {e}")
        _logger.info("💡 INFO: Tentative d'archivage PDF échouée")
        return None


def save_report(
    original_note: str,
    step_logs: list[str],
    ai_stream: str,
    processed_note: str,
    correction_debrief: str,
    token_stats: ports.AITokenStats | None = None,
) -> str | None:
    """Sauvegarde le rapport complet de la session en PDF, dans reports/.
    Renvoie le chemin du PDF, None si rien n'a été produit"""
    if not processed_note or not processed_note.strip():
        _logger.info("⚠️ ATTENTION: Aucun contenu traité à sauvegarder")
        return None

    # Créer le dossier reports s'il n'existe pas
    os.makedirs(config.REPORTS_DIR, exist_ok=True)

    # Nom de fichier horodaté
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_path = os.path.join(config.REPORTS_DIR, f"rapport_complet_{timestamp}.pdf")

    _logger.info(f"💾 SAUVEGARDE: Création du fichier PDF {pdf_path}")

    # Contenu complet avec TOUS les logs
    _logger.info("🔧 ÉTAPE: Préparation du rapport complet...")
    markdown = report.build_report_markdown(
        original_note=original_note,
        step_logs=step_logs,
        ai_stream=ai_stream,
        processed_note=processed_note,
        correction_debrief=correction_debrief,
        token_stats=token_stats,
        model=config.GEMINI_MODEL,
        thinking_level=config.GEMINI_THINKING_LEVEL.value,
        generated_at=datetime.now(),
    )
    _logger.info("✅ SUCCÈS: Rapport complet préparé")

    pdf_path = generate_pdf(markdown, pdf_path)

    # Bilan final
    _logger.info("\n📊 BILAN SAUVEGARDE PDF:")
    _logger.info("=" * 30)
    if pdf_path:
        _logger.info(f"✅ PDF      : {os.path.basename(pdf_path)}")
    else:
        _logger.info("❌ PDF      : ÉCHEC")
    _logger.info("=" * 30)

    return pdf_path
