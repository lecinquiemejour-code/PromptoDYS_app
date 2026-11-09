"""Ports du domaine : ce dont les cas d'usage ont besoin du monde extérieur, et les données échangées.

Les adaptateurs (Eel, Gemini, disque) héritent explicitement de leur Protocol, pour que le lien
se voie à la lecture. Comme les méthodes ne sont pas marquées @abstractmethod, rien n'oblige
un adaptateur à toutes les redéfinir : une méthode oubliée hérite du corps vide du Protocol (...)
et renvoie None au lieu de lever une erreur.
Les faux des tests n'en héritent pas : une méthode manquante y lève AttributeError dès son appel.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

# --- Données échangées ---


@dataclass(frozen=True)
class Image:
    """Image d'un document, en binaire (la conversion base64 relève de l'adaptateur)."""

    filename: str
    content: bytes
    mime_type: str


@dataclass
class Document:
    """Document complet de l'éditeur : texte Markdown et images qu'il référence."""

    markdown: str
    images: list[Image] = field(default_factory=list[Image])


# Jetons consommés par l'IA : clés input, output, thinking, total
AITokenStats = dict[str, object]


@dataclass(frozen=True)
class AIChunk:
    """Morceau de réponse de l'IA : texte de réflexion ou de réponse.
    Le dernier morceau du flux peut porter seulement les statistiques de jetons (usage)."""

    text: str = ""
    thought: bool = False
    usage: AITokenStats | None = None


class AIModelError(Exception):
    """Échec de l'IA (serveur, quota, clé refusée...), le message est destiné à l'utilisateur."""


# --- Ports ---


class Editor(Protocol):
    """L'éditeur où l'élève écrit sa note."""

    def read_markdown(self) -> str:
        """Texte Markdown actuel (vide en cas d'erreur)."""
        ...

    def write_markdown(self, markdown: str) -> bool:
        """Remplace le texte de l'éditeur. Faux en cas d'erreur."""
        ...

    def read_document(self) -> Document | None:
        """Document complet (texte et images). None en cas d'erreur."""
        ...

    def write_document(self, document: Document) -> bool:
        """Charge un document complet dans l'éditeur. Faux en cas d'erreur."""
        ...


class AIModel(Protocol):
    """Modèle d'IA qui corrige la note."""

    def stream(self, prompt: str) -> Iterator[AIChunk]:
        """Envoie le prompt et renvoie la réponse morceau par morceau. Lève AIModelError en cas d'échec."""
        ...


class DocumentStore(Protocol):
    """Enregistre et ouvre les documents, « façon Arduino » : <dossier>/<nom>/<nom>.md et images/."""

    def save(self, document: Document, directory: str, name: str) -> str | None:
        """Enregistre le document dans directory/name. Renvoie le dossier du document, None en cas d'erreur."""
        ...

    def load(self, path: str) -> tuple[Document, str] | None:
        """Lit le document désigné par son dossier ou par son fichier .md.
        Renvoie (document, dossier du document), None en cas d'erreur."""
        ...
