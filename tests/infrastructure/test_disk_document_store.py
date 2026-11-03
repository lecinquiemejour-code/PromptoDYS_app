"""DiskDocumentStore sur un vrai disque (dossier temporaire)."""

from promptodys.domain import ports
from promptodys.infrastructure.disk_document_store import DiskDocumentStore

PNG = b"\x89PNG\r\n\x1a\n donnees"


def _document(image_filename="schema.png"):
    return ports.Document(
        markdown="# Cours\n![schema](./images/schema.png)",
        images=[ports.Image(filename=image_filename, content=PNG, mime_type="image/png")],
    )


def test_save_creates_arduino_layout(tmp_path):
    """Le document est rangé dans <dossier>/<nom>/<nom>.md, ses images dans images/."""
    doc_dir = DiskDocumentStore().save(_document(), str(tmp_path), "cours")
    assert doc_dir == str(tmp_path / "cours")
    assert (tmp_path / "cours" / "cours.md").read_text(encoding="utf-8") == _document().markdown
    assert (tmp_path / "cours" / "images" / "schema.png").read_bytes() == PNG


def test_round_trip_from_md_file_or_folder(tmp_path):
    """Un document enregistré se relit à l'identique, par son fichier .md comme par son dossier."""
    store = DiskDocumentStore()
    doc_dir = store.save(_document(), str(tmp_path), "cours")
    assert store.load(str(tmp_path / "cours" / "cours.md")) == (_document(), doc_dir)
    assert store.load(doc_dir) == (_document(), doc_dir)


def test_load_ignores_non_images(tmp_path):
    """Un fichier qui n'est pas une image, dans images/, n'est pas chargé."""
    store = DiskDocumentStore()
    doc_dir = store.save(_document(), str(tmp_path), "cours")
    (tmp_path / "cours" / "images" / "notes.txt").write_text("pas une image")
    document, _ = store.load(doc_dir)
    assert [image.filename for image in document.images] == ["schema.png"]


def test_load_invalid_path(tmp_path):
    """Un chemin qui n'existe pas, ou un dossier sans .md du même nom, ne donne aucun document."""
    store = DiskDocumentStore()
    assert store.load(str(tmp_path / "absent")) is None
    (tmp_path / "vide").mkdir()
    assert store.load(str(tmp_path / "vide")) is None


def test_save_keeps_images_inside_images_folder(tmp_path):
    """Un nom d'image venu du JavaScript ne peut pas écrire hors de images/ (constat M6)."""
    DiskDocumentStore().save(_document("../../evasion.png"), str(tmp_path), "cours")
    assert (tmp_path / "cours" / "images" / "evasion.png").read_bytes() == PNG
    assert not (tmp_path / "evasion.png").exists()


def test_save_skips_unusable_image_name(tmp_path):
    """Un nom d'image vide ou réduit à '..' est ignoré, le document est quand même enregistré."""
    store = DiskDocumentStore()
    for bad_name in ("", "..", "images/"):
        assert store.save(_document(bad_name), str(tmp_path), "cours") == str(tmp_path / "cours")
    assert list((tmp_path / "cours" / "images").iterdir()) == []
