"""Adaptateur du port DocumentStore : enregistre et ouvre les documents sur le disque, « façon Arduino »."""

import logging
import mimetypes
import os

from promptodys.domain import ports

_logger = logging.getLogger(__name__)


def _safe_image_filename(filename: str) -> str | None:
    """Nom d'image réduit à son dernier composant, pour ne jamais écrire hors de images/ (constat M6).
    Le nom vient du JavaScript : "../../x.png" devient "x.png". None si rien d'utilisable ne reste."""
    name = os.path.basename(filename)
    if name in ("", ".", ".."):
        return None
    return name


class DiskDocumentStore(ports.DocumentStore):
    """Documents sur le disque, « façon Arduino » :

    directory/name/
    ├── name.md
    └── images/
        ├── photo_xxx.png
        └── schema_xxx.jpg
    """

    def save(self, document: ports.Document, directory: str, name: str) -> str | None:
        """Écrit le document (style Arduino : on écrase le contenu existant).
        Renvoie le dossier du document, None si le .md n'a pas pu être écrit"""
        _logger.info(f"💾 SAUVEGARDE: Début pour '{name}' dans '{directory}'")
        doc_dir = os.path.join(directory, name)
        images_dir = os.path.join(doc_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        _logger.info(f"📁 SAUVEGARDE: Dossier créé/existant: {doc_dir}")

        md_path = os.path.join(doc_dir, f"{name}.md")
        try:
            with open(md_path, "w", encoding="utf-8") as f:
                f.write(document.markdown)
            _logger.info(f"✅ SAUVEGARDE: Fichier MD écrit: {md_path}")
        except Exception as e:
            _logger.error(f"❌ SAUVEGARDE: Erreur écriture MD: {e}")
            return None

        images_saved = 0
        for image in document.images:
            filename = _safe_image_filename(image.filename)
            if filename is None:
                _logger.error(f"  ❌ Nom d'image inutilisable, image ignorée: '{image.filename}'")
                continue
            try:
                with open(os.path.join(images_dir, filename), "wb") as f:
                    f.write(image.content)
                images_saved += 1
                _logger.info(f"  🖼️ Image sauvée: {filename} ({len(image.content)} octets)")
            except Exception as e:
                _logger.error(f"  ❌ Erreur image '{filename}': {e}")

        _logger.info(f"✅ SAUVEGARDE TERMINÉE: {md_path} + {images_saved} image(s)")
        return doc_dir

    def load(self, path: str) -> tuple[ports.Document, str] | None:
        """Lit le document désigné par son dossier OU par son fichier .md (principe Arduino :
        les deux fonctionnent pareil). Renvoie (document, dossier du document), None en cas d'erreur"""
        _logger.info(f"📂 OUVERTURE: Chemin reçu: '{path}'")

        if path.endswith(".md") and os.path.isfile(path):
            doc_dir = os.path.dirname(path)
            _logger.info(f"📂 OUVERTURE: Fichier .md détecté → dossier déduit: {doc_dir}")
        elif os.path.isdir(path):
            doc_dir = path
            _logger.info("📂 OUVERTURE: Dossier sélectionné directement")
        else:
            _logger.error(f"❌ OUVERTURE: Chemin invalide (ni dossier, ni fichier .md): {path}")
            return None

        # Convention : nom du dossier = nom du fichier .md
        document_name = os.path.basename(doc_dir)
        md_path = os.path.join(doc_dir, f"{document_name}.md")
        images_dir = os.path.join(doc_dir, "images")

        if not os.path.exists(md_path):
            _logger.error(f"❌ OUVERTURE: Fichier non trouvé: {md_path}")
            return None
        try:
            with open(md_path, encoding="utf-8") as f:
                markdown = f.read()
            _logger.info(f"📄 OUVERTURE: Markdown lu ({len(markdown)} caractères)")
        except Exception as e:
            _logger.error(f"❌ OUVERTURE: Erreur lecture MD: {e}")
            return None

        images: list[ports.Image] = []
        if os.path.exists(images_dir):
            for filename in os.listdir(images_dir):
                image_path = os.path.join(images_dir, filename)
                if not os.path.isfile(image_path):
                    continue
                mime_type, _ = mimetypes.guess_type(image_path)
                if not mime_type or not mime_type.startswith("image/"):
                    _logger.debug(f"  🔍 Fichier ignoré (pas une image): {filename}")
                    continue
                try:
                    with open(image_path, "rb") as f:
                        images.append(ports.Image(filename=filename, content=f.read(), mime_type=mime_type))
                    _logger.info(f"  🖼️ Image chargée: {filename} ({mime_type})")
                except Exception as e:
                    _logger.error(f"  ❌ Erreur lecture image '{filename}': {e}")
        else:
            _logger.info("📁 OUVERTURE: Pas de dossier images/ (document texte seul)")

        return ports.Document(markdown=markdown, images=images), doc_dir
