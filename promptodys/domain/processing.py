"""Cas d'usage principal : faire corriger la note de l'éditeur par l'IA.

process_note renvoie un résultat et ne touche jamais à l'interface : c'est l'appelant qui décide
de l'état des boutons et du statut affiché, ce qui empêche les bugs B1 et B2 de revenir.
"""

import enum
import logging
import threading
from dataclasses import dataclass, field
from datetime import date

from promptodys.domain import note, ports

_logger = logging.getLogger(__name__)


class ProcessingStatus(enum.Enum):
    COMPLETED = "completed"  # note corrigée et injectée (ou injection tentée)
    FAILED = "failed"  # erreur de l'IA : rien n'a été écrit dans l'éditeur
    CANCELLED = "cancelled"  # abandon demandé : rien n'a été écrit dans l'éditeur


@dataclass
class ProcessingResult:
    """Tout ce qu'il faut pour afficher le résultat et produire le rapport."""

    status: ProcessingStatus
    original_note: str = ""
    processed_note: str = ""
    correction_debrief: str = ""
    # Réflexion (préfixée par 💭) et réponse de l'IA, telles que reçues
    ai_stream: str = ""
    token_stats: ports.AITokenStats = field(default_factory=dict)
    # Logs des étapes de préparation (avant l'envoi à l'IA), repris dans le rapport
    step_logs: list[str] = field(default_factory=list)


def process_note(
    editor: ports.Editor,
    model: ports.AIModel,
    prompt_template: str,
    cancel: threading.Event,
    today: date,
) -> ProcessingResult:
    """Lit la note de l'éditeur, la fait corriger par l'IA, puis injecte la note corrigée.

    Étapes 3 à 8 du traitement (1 et 2, client et modèle de prompt, sont faites par l'appelant).
    cancel : jeton d'abandon, vérifié à chaque morceau de réponse. Un traitement abandonné
    s'arrête à la sortie du flux sans rien écrire dans l'éditeur.
    """
    step_logs = []

    def log_step(message):
        """Log d'une étape de préparation, gardé aussi pour le rapport."""
        _logger.info(message)
        step_logs.append(message)

    # 3. Lire le contenu de l'éditeur
    log_step("\n📖 ÉTAPE 3: Lecture du contenu éditeur...")
    original_note = editor.read_markdown()

    # 4. Substituer [TEXTE] et [DATE]
    log_step("\n🔗 ÉTAPE 4: Préparation du prompt final...")
    prompt = note.build_prompt(prompt_template, original_note, today)
    log_step("✅ SUCCÈS: Prompt préparé (substitution [TEXTE] et [DATE] effectuée)")

    result = ProcessingResult(status=ProcessingStatus.FAILED, original_note=original_note, step_logs=step_logs)

    # 5. Envoi à l'IA et réception du flux
    _logger.info("\n🚀 ÉTAPE 5: Envoi à Gemini et traitement en cours...")
    _logger.info("🔄 Streaming en direct (💭 = thinking, texte normal = réponse):")
    _logger.info("-" * 60)

    answer = ""
    ai_stream = ""
    token_stats = None
    try:
        _logger.info("📡 Flux IA: Démarrage de la réception des données...")
        for chunk in model.stream(prompt):
            # Abandon vérifié à chaque morceau, traité à la sortie du flux
            if cancel.is_set():
                break
            if chunk.usage is not None:
                token_stats = chunk.usage
            if not chunk.text:
                continue
            if chunk.thought:
                thinking_text = f"💭 {chunk.text}"
                _logger.info(thinking_text)
                ai_stream += thinking_text + "\n"
            else:
                _logger.info(chunk.text)
                answer += chunk.text
                ai_stream += chunk.text
    # Après un abandon, une erreur de connexion n'est pas un échec à signaler
    except ports.AIModelError as e:
        if cancel.is_set():
            return _cancelled(result)
        _logger.error(f"\n❌ ÉCHEC: {e}")
        return result
    except Exception as e:
        if cancel.is_set():
            return _cancelled(result)
        _logger.error(f"\n❌ ÉCHEC: Erreur inattendue: {e}")
        return result

    # Abandon par break dans la boucle, ou pendant l'attente du dernier morceau
    if cancel.is_set():
        _logger.warning("⚠️ INFOS: Injection et sauvegarde PDF annulées.")
        return _cancelled(result)

    result.ai_stream = ai_stream
    _logger.info("\n" + "-" * 60)
    _logger.info("✅ SUCCÈS: Réponse Gemini complète reçue")

    # 6. Extraire la note corrigée (sans balises <NOTE>, extract_note_content le signale elle-même)
    _logger.info("\n🔍 ÉTAPE 6: Extraction du contenu traité...")
    processed_note = note.extract_note_content(answer)
    if note.has_note_tags(answer):
        _logger.info("✅ SUCCÈS: Balises <NOTE> détectées et contenu extrait")
        _logger.info(f"📏 Taille du contenu traité: {len(processed_note)} caractères")
    # Section « Note d'origine » ajoutée côté Python (n'est plus générée par Gemini)
    processed_note = note.append_original_note(processed_note, original_note)
    result.processed_note = processed_note
    result.correction_debrief = note.extract_correction_debrief(answer)

    # 7. Injecter dans l'éditeur (un échec est signalé sans faire échouer le traitement)
    _logger.info("\n✏️ ÉTAPE 7: Injection dans l'éditeur...")
    if not processed_note:
        _logger.error("❌ ÉCHEC: Aucun contenu à injecter")
    elif editor.write_markdown(processed_note):
        _logger.info("✅ SUCCÈS: Contenu injecté avec succès !")
    else:
        _logger.error("❌ ÉCHEC: Erreur lors de l'injection dans l'éditeur")

    # 8. Bilan des jetons
    _logger.info("\n📊 ÉTAPE 8: Bilan final des tokens...")
    _log_token_stats(token_stats)
    result.token_stats = token_stats or {}

    result.status = ProcessingStatus.COMPLETED
    return result


def _cancelled(result: ProcessingResult) -> ProcessingResult:
    result.status = ProcessingStatus.CANCELLED
    return result


def _log_token_stats(token_stats: ports.AITokenStats | None) -> None:
    _logger.info("=" * 30)
    _logger.info("📊 STATISTIQUES GEMINI")
    _logger.info("=" * 30)
    if token_stats:
        _logger.info(f"🔢 Input tokens     : {token_stats.get('input', 'N/A')}")
        _logger.info(f"🔢 Output tokens    : {token_stats.get('output', 'N/A')}")
        _logger.info(f"🧠 Thinking tokens  : {token_stats.get('thinking', 'N/A')}")
        _logger.info(f"🔢 Total tokens     : {token_stats.get('total', 'N/A')}")
    else:
        _logger.warning("⚠️ Statistiques non disponibles pour cette réponse")
    _logger.info("=" * 30)
