"""Modèle Gemini (SDK google-genai) : adaptateur du port AIModel."""

import logging
from collections.abc import Iterator

import google.genai.errors as genai_errors
from google import genai
from google.genai import types

from promptodys.domain import ports
from promptodys.infrastructure import config

_logger = logging.getLogger(__name__)


def create_client() -> genai.Client | None:
    """Client Gemini authentifié par la clé de GeminiKey.txt. None si la clé manque ou est invalide"""
    try:
        api_key = config.read_api_key()
        if not api_key:
            _logger.info("❌ ÉCHEC: Aucune clé API trouvée dans GeminiKey.txt")
            return None
        if api_key == config.GEMINI_API_KEY_PLACEHOLDER:
            _logger.info("❌ ÉCHEC: GeminiKey.txt contient encore la valeur du template, remplacez-la par votre clé")
            return None
        # Seuls les 4 derniers caractères : ce log est recopié dans les rapports PDF
        _logger.info(f"🔑 INFO: Clé API chargée (...{api_key[-4:]})")
        return genai.Client(api_key=api_key)
    except FileNotFoundError:
        _logger.info(f"❌ ÉCHEC: Fichier GeminiKey.txt introuvable dans {config.APP_DIR}")
        return None
    except Exception as e:
        _logger.info(f"❌ ÉCHEC: Erreur initialisation Gemini: {e}")
        return None


class GeminiModel(ports.AIModel):
    """Modèle Gemini"""

    def __init__(self, client: genai.Client):
        self.client = client
        self.generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level=config.GEMINI_THINKING_LEVEL,
                include_thoughts=True,
            ),
        )

    def stream(self, prompt: str) -> Iterator[ports.AIChunk]:
        """Morceaux de réflexion et de réponse, puis un dernier morceau avec les jetons consommés.
        Les erreurs de Gemini deviennent des ports.AIModelError"""
        last_response = None
        try:
            for response in self.client.models.generate_content_stream(
                model=config.GEMINI_MODEL, contents=prompt, config=self.generate_content_config
            ):
                last_response = response
                if not response.candidates:
                    continue
                if not response.candidates[0].content or not response.candidates[0].content.parts:
                    continue
                for part in response.candidates[0].content.parts:
                    if part.text:
                        yield ports.AIChunk(text=part.text, thought=bool(part.thought))
        except genai_errors.ServerError as e:
            raise ports.AIModelError(f"Erreur serveur Gemini: {e}") from e
        except genai_errors.APIError as e:
            raise ports.AIModelError(f"Erreur API Gemini: {e}") from e

        usage = getattr(last_response, "usage_metadata", None)
        if usage:
            yield ports.AIChunk(
                usage={
                    "input": getattr(usage, "prompt_token_count", "N/A"),
                    "output": getattr(usage, "candidates_token_count", "N/A"),
                    "thinking": getattr(usage, "thoughts_token_count", "N/A"),
                    "total": getattr(usage, "total_token_count", "N/A"),
                }
            )
