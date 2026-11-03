import os

import pytest

from promptodys.infrastructure import config


def test_app_dir_is_repository_root():
    """En développement, APP_DIR est la racine du dépôt, pas le dossier du module config."""
    assert os.path.isfile(os.path.join(config.APP_DIR, "pyproject.toml"))
    assert os.path.join(config.APP_DIR, "reports") == config.REPORTS_DIR


def test_read_api_key_skips_blank_lines_comments_and_bom(tmp_path, monkeypatch):
    """La clé est la première ligne ni vide ni commentée, BOM du Bloc-notes toléré."""
    key_file = tmp_path / "GeminiKey.txt"
    key_file.write_text("\n# ma clé :\n  ABCD1234  \nautre\n", encoding="utf-8-sig")
    monkeypatch.setattr(config, "GEMINI_API_KEY_FILE", str(key_file))

    assert config.read_api_key() == "ABCD1234"


def test_read_api_key_returns_empty_string_without_key(tmp_path, monkeypatch):
    """Un fichier sans clé renvoie une chaîne vide."""
    key_file = tmp_path / "GeminiKey.txt"
    key_file.write_text("# rien ici\n\n", encoding="utf-8")
    monkeypatch.setattr(config, "GEMINI_API_KEY_FILE", str(key_file))

    assert config.read_api_key() == ""


def test_read_api_key_raises_if_file_is_missing(tmp_path, monkeypatch):
    """Fichier absent : FileNotFoundError, que init_gemini_client() transforme en message."""
    monkeypatch.setattr(config, "GEMINI_API_KEY_FILE", str(tmp_path / "absent.txt"))

    with pytest.raises(FileNotFoundError):
        config.read_api_key()


def test_find_web_folder_finds_build_web():
    """En développement, build_web/ est trouvé à la racine du dépôt."""
    if not os.path.isfile(os.path.join(config.APP_DIR, "build_web", "index.html")):
        pytest.skip("build_web/ absent de ce poste")
    assert config.find_web_folder() == os.path.join(config.APP_DIR, "build_web")


def test_prompt_template_is_read_from_repository_in_development():
    """En développement, le modèle de prompt est celui du dépôt, et il contient la balise [TEXTE]."""
    assert os.path.join(config.APP_DIR, "promptodys.prompt") == config.PROMPT_TEMPLATE_FILE
    template = config.read_prompt_template()
    assert template is not None and "[TEXTE]" in template


def test_read_prompt_template_requires_text_placeholder(tmp_path, monkeypatch):
    """Un modèle sans balise [TEXTE] est refusé : la note de l'élève n'y serait jamais insérée."""
    template_file = tmp_path / "promptodys.prompt"
    template_file.write_text("Corrige la note du [DATE].", encoding="utf-8")
    monkeypatch.setattr(config, "PROMPT_TEMPLATE_FILE", str(template_file))

    assert config.read_prompt_template() is None


def test_read_prompt_template_missing_file(tmp_path, monkeypatch):
    """Modèle absent : None, pas d'exception."""
    monkeypatch.setattr(config, "PROMPT_TEMPLATE_FILE", str(tmp_path / "absent.prompt"))

    assert config.read_prompt_template() is None
