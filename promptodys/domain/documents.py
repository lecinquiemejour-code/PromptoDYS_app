"""Règles sur les documents PromptoDYS, rangés « façon Arduino » :
un dossier du nom du document, qui contient <nom>.md et images/.
"""

import logging
import os
import re

from promptodys.domain import ports

_logger = logging.getLogger(__name__)


def prepare_save_path(chosen_path: str) -> tuple[str, str]:
    """Renvoie (dossier parent, nom du document) à partir du chemin choisi dans le dialogue.

    Le nom est assaini. Il est renvoyé vide s'il ne reste rien après assainissement
    ou s'il commence par un point : c'est à l'appelant de le refuser.
    Si l'utilisateur est entré dans le dossier du document, on remonte au dossier parent
    (évite equations/equations/equations.md)."""
    save_dir = os.path.dirname(chosen_path)
    doc_name = os.path.splitext(os.path.basename(chosen_path))[0]
    doc_name = re.sub(r'[<>:"/\\|?*]', "_", doc_name).strip()
    # Nom de fichier caché ('.md', '.foo', '..') : refusé comme un nom vide
    if doc_name.startswith("."):
        doc_name = ""
    # Points et espaces finaux retirés : Windows les supprime des noms de dossier
    doc_name = doc_name.rstrip(" .")

    # Anti-récursion : l'utilisateur a navigué à l'intérieur du dossier du document
    while os.path.basename(save_dir) == doc_name:
        parent = os.path.dirname(save_dir)
        if parent == save_dir:  # racine du disque : on ne peut plus remonter
            break
        _logger.warning(f"⚠️ Anti-récursion: save_dir '{save_dir}' se termine par '{doc_name}' → on remonte")
        save_dir = parent
    return save_dir, doc_name


def save_document(editor: ports.Editor, store: ports.DocumentStore, directory: str, name: str) -> str | None:
    """Enregistre le document de l'éditeur dans directory/name.
    Renvoie le dossier du document, None si l'éditeur ou le disque a échoué."""
    document = editor.read_document()
    if document is None:
        _logger.error("❌ SAUVEGARDE: Aucune donnée reçue de l'éditeur")
        return None
    return store.save(document, directory, name)


def open_document(editor: ports.Editor, store: ports.DocumentStore, path: str) -> str | None:
    """Charge dans l'éditeur le document désigné par son dossier ou par son fichier .md.
    Renvoie le dossier du document, None si le disque ou l'éditeur a échoué."""
    loaded = store.load(path)
    if loaded is None:
        return None
    document, document_dir = loaded
    if not editor.write_document(document):
        return None
    return document_dir
