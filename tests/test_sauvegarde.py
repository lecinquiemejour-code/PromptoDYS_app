import os

import askGeminiPrompto as app

DOCS = os.path.join(os.sep, "Users", "eleve", "PromptoDYS")


def test_preparer_chemin_sauvegarde_cas_simple():
    """Le dossier choisi et le nom sans extension sont renvoyés."""
    chemin = os.path.join(DOCS, "equations.md")
    assert app.preparer_chemin_sauvegarde(chemin) == (DOCS, "equations")


def test_preparer_chemin_sauvegarde_sans_extension():
    """Un nom saisi sans extension est gardé tel quel."""
    chemin = os.path.join(DOCS, "equations")
    assert app.preparer_chemin_sauvegarde(chemin) == (DOCS, "equations")


def test_preparer_chemin_sauvegarde_assainit_le_nom():
    """Les caractères interdits par Windows sont remplacés, les espaces autour retirés."""
    chemin = os.path.join(DOCS, ' cours:1*"maths"? .md')
    assert app.preparer_chemin_sauvegarde(chemin) == (DOCS, 'cours_1__maths__')


def test_preparer_chemin_sauvegarde_remonte_du_dossier_document():
    """Entré dans le dossier du document, on remonte d'un niveau (pas de equations/equations/)."""
    chemin = os.path.join(DOCS, "equations", "equations.md")
    assert app.preparer_chemin_sauvegarde(chemin) == (DOCS, "equations")


def test_preparer_chemin_sauvegarde_remonte_plusieurs_niveaux():
    """Une imbrication déjà doublée est entièrement remontée."""
    chemin = os.path.join(DOCS, "equations", "equations", "equations.md")
    assert app.preparer_chemin_sauvegarde(chemin) == (DOCS, "equations")
