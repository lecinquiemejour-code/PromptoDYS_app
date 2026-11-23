"""Marques posées sur les logs, lues par leurs destinations.

Un message de log dit ce qui se passe ; sa mise en page revient à la destination. Pour aérer
l'affichage, le code marque le message au lieu d'y glisser des retours à la ligne :

    _logger.info("📖 ÉTAPE 3: Lecture du contenu éditeur...", extra=log_marks.SECTION)

SECTION : le message ouvre une nouvelle partie (étape du traitement, démarrage, abandon...).
La console du panneau insère une ligne vide avant lui ; le fichier de log et le rapport PDF
l'écrivent tel quel.

Dans le domaine pour que toutes les couches puissent l'importer.
"""

import logging

_SECTION_ATTRIBUTE = "section"

SECTION: dict[str, object] = {_SECTION_ATTRIBUTE: True}


def is_section(record: logging.LogRecord) -> bool:
    """Vrai si le message a été émis avec extra=SECTION"""
    return getattr(record, _SECTION_ATTRIBUTE, False) is True
