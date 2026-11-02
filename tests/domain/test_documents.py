import logging
import os

from promptodys.domain.documents import prepare_save_path

DOCS = os.path.join(os.sep, "Users", "eleve", "PromptoDYS")


def test_prepare_save_path_simple_case():
    """Le dossier choisi et le nom sans extension sont renvoyés."""
    path = os.path.join(DOCS, "equations.md")
    assert prepare_save_path(path) == (DOCS, "equations")


def test_prepare_save_path_without_extension():
    """Un nom saisi sans extension est gardé tel quel."""
    path = os.path.join(DOCS, "equations")
    assert prepare_save_path(path) == (DOCS, "equations")


def test_prepare_save_path_sanitizes_name():
    """Les caractères interdits par Windows sont remplacés, les espaces autour retirés."""
    path = os.path.join(DOCS, ' cours:1*"maths"? .md')
    assert prepare_save_path(path) == (DOCS, "cours_1__maths__")


def test_prepare_save_path_goes_up_from_document_folder():
    """Entré dans le dossier du document, on remonte d'un niveau (pas de equations/equations/)."""
    path = os.path.join(DOCS, "equations", "equations.md")
    assert prepare_save_path(path) == (DOCS, "equations")


def test_prepare_save_path_goes_up_several_levels():
    """Une imbrication déjà doublée est entièrement remontée."""
    path = os.path.join(DOCS, "equations", "equations", "equations.md")
    assert prepare_save_path(path) == (DOCS, "equations")


def test_prepare_save_path_empty_name():
    """Un nom réduit à rien par l'assainissement est renvoyé vide, pour être refusé par l'appelant."""
    path = os.path.join(DOCS, "  .md")
    assert prepare_save_path(path) == (DOCS, "")


def test_prepare_save_path_extension_only():
    """'.md' seul est une extension sans nom, pas un nom de fichier caché : le nom est renvoyé vide."""
    path = os.path.join(DOCS, ".md")
    assert prepare_save_path(path) == (DOCS, "")


def test_prepare_save_path_empty_name_at_root():
    """À la racine du disque, l'anti-récursion s'arrête au lieu de boucler (B8)."""
    path = os.path.join(os.sep, "  .md")
    assert prepare_save_path(path) == (os.sep, "")


def test_prepare_save_path_name_made_of_dots():
    """'.' et '..' commencent par un point (ils désigneraient le dossier courant ou le parent) : nom vide."""
    assert prepare_save_path(os.path.join(DOCS, "..")) == (DOCS, "")
    assert prepare_save_path(os.path.join(DOCS, ".")) == (DOCS, "")


def test_prepare_save_path_rejects_hidden_file():
    """Un nom de fichier caché (commençant par un point, même après des espaces) est renvoyé vide."""
    assert prepare_save_path(os.path.join(DOCS, ".foo")) == (DOCS, "")
    assert prepare_save_path(os.path.join(DOCS, " .foo")) == (DOCS, "")


def test_prepare_save_path_strips_trailing_dots():
    """Windows retire les points finaux des noms de dossier : on les retire aussi du nom du document."""
    path = os.path.join(DOCS, "cours..md")
    assert prepare_save_path(path) == (DOCS, "cours")


def test_prepare_save_path_logs_each_level_climbed(caplog):
    """Chaque niveau remonté par l'anti-récursion est signalé en avertissement."""
    caplog.set_level(logging.INFO, logger="promptodys")
    prepare_save_path(os.path.join(DOCS, "equations", "equations", "equations.md"))
    assert len(caplog.records) == 2
    assert all(record.levelno == logging.WARNING for record in caplog.records)
    assert "Anti-récursion" in caplog.messages[0]
