"""Marques posées sur les logs, lues par leurs destinations.

Un message de log dit ce qui se passe ; sa mise en page revient à la destination. Pour aérer
l'affichage, le code marque le message au lieu d'y glisser des retours à la ligne :

    _logger.info("📖 ÉTAPE 3: Lecture du contenu éditeur...", extra=log_marks.SECTION)

SECTION : le message ouvre une nouvelle partie (étape du traitement, démarrage, abandon...).
La console du panneau et le rapport PDF insèrent une ligne vide avant lui ; le fichier de log
l'écrit tel quel.

FRAGMENT : le message est un morceau d'un texte reçu par bouts (la réponse de l'IA, découpée
n'importe où). La console du panneau écrit les fragments à la suite, sans retour à la ligne ;
le fichier de log écrit chaque morceau sur sa ligne.

Dans le domaine pour que toutes les couches puissent l'importer.
"""

import logging

_SECTION_ATTRIBUTE = "section"
_FRAGMENT_ATTRIBUTE = "fragment"

SECTION: dict[str, object] = {_SECTION_ATTRIBUTE: True}
FRAGMENT: dict[str, object] = {_FRAGMENT_ATTRIBUTE: True}


def is_section(record: logging.LogRecord) -> bool:
    """Vrai si le message a été émis avec extra=SECTION"""
    return getattr(record, _SECTION_ATTRIBUTE, False) is True


def is_fragment(record: logging.LogRecord) -> bool:
    """Vrai si le message a été émis avec extra=FRAGMENT"""
    return getattr(record, _FRAGMENT_ATTRIBUTE, False) is True
