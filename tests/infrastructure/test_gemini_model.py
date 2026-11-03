"""GeminiModel et create_client, sans réseau : SDK google-genai simulé."""

from types import SimpleNamespace

import google.genai.errors as genai_errors
import pytest
from google import genai

from promptodys.domain import ports
from promptodys.infrastructure import config, gemini_model
from promptodys.infrastructure.gemini_model import GeminiModel


def _response(parts, usage=None):
    """Morceau de réponse au format du SDK google-genai (seuls les attributs lus)."""
    content = SimpleNamespace(parts=[SimpleNamespace(text=text, thought=thought) for text, thought in parts])
    return SimpleNamespace(candidates=[SimpleNamespace(content=content)], usage_metadata=usage)


def test_gemini_model_converts_responses_to_chunks():
    """Réflexion et réponse deviennent des AIChunk, les parties vides sont ignorées, les jetons arrivent en dernier."""
    usage = SimpleNamespace(
        prompt_token_count=10, candidates_token_count=20, thoughts_token_count=5, total_token_count=35
    )
    responses = [
        _response([("je réfléchis", True), ("", False)]),
        SimpleNamespace(candidates=[], usage_metadata=None),
        _response([("<NOTE>ok</NOTE>", None)], usage=usage),
    ]
    client = SimpleNamespace(models=SimpleNamespace(generate_content_stream=lambda **kwargs: iter(responses)))

    chunks = list(GeminiModel(client).stream("prompt"))

    assert chunks == [
        ports.AIChunk(text="je réfléchis", thought=True),
        ports.AIChunk(text="<NOTE>ok</NOTE>", thought=False),
        ports.AIChunk(usage={"input": 10, "output": 20, "thinking": 5, "total": 35}),
    ]


def _stream_raising(error):
    def generate_content_stream(**kwargs):
        raise error
        yield  # générateur, comme le SDK

    return SimpleNamespace(models=SimpleNamespace(generate_content_stream=generate_content_stream))


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (genai_errors.ServerError(503, {"error": {"message": "surcharge"}}), "Erreur serveur Gemini"),
        (genai_errors.ClientError(429, {"error": {"message": "quota"}}), "Erreur API Gemini"),
    ],
)
def test_gemini_model_converts_sdk_errors(error, message):
    """Les erreurs du SDK deviennent des AIModelError, avec un message pour l'élève."""
    with pytest.raises(ports.AIModelError, match=message):
        list(GeminiModel(_stream_raising(error)).stream("prompt"))


def _key_file(tmp_path, monkeypatch, content):
    key_file = tmp_path / "GeminiKey.txt"
    key_file.write_text(content, encoding="utf-8")
    monkeypatch.setattr(config, "GEMINI_API_KEY_FILE", str(key_file))


def test_create_client_with_a_key(tmp_path, monkeypatch):
    """Une clé présente donne un client (aucun appel réseau à la création)."""
    _key_file(tmp_path, monkeypatch, "AIza-cle-de-test\n")
    assert isinstance(gemini_model.create_client(), genai.Client)


@pytest.mark.parametrize("content", ["# rien\n", f"{config.GEMINI_API_KEY_PLACEHOLDER}\n"])
def test_create_client_without_usable_key(tmp_path, monkeypatch, content):
    """Fichier sans clé, ou encore à la valeur du template : pas de client."""
    _key_file(tmp_path, monkeypatch, content)
    assert gemini_model.create_client() is None


def test_create_client_without_key_file(tmp_path, monkeypatch):
    """GeminiKey.txt absent : pas de client, pas d'exception."""
    monkeypatch.setattr(config, "GEMINI_API_KEY_FILE", str(tmp_path / "absent.txt"))
    assert gemini_model.create_client() is None
