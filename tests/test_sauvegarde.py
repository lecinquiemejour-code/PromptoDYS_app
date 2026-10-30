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


def test_preparer_chemin_sauvegarde_nom_vide():
    """Un nom réduit à rien par l'assainissement est renvoyé vide, pour être refusé par l'appelant."""
    chemin = os.path.join(DOCS, "  .md")
    assert app.preparer_chemin_sauvegarde(chemin) == (DOCS, "")


def test_preparer_chemin_sauvegarde_extension_seule():
    """'.md' seul est une extension sans nom, pas un nom de fichier caché : le nom est renvoyé vide."""
    chemin = os.path.join(DOCS, ".md")
    assert app.preparer_chemin_sauvegarde(chemin) == (DOCS, "")


def test_preparer_chemin_sauvegarde_nom_vide_a_la_racine():
    """À la racine du disque, l'anti-récursion s'arrête au lieu de boucler (B8)."""
    chemin = os.path.join(os.sep, "  .md")
    assert app.preparer_chemin_sauvegarde(chemin) == (os.sep, "")


def test_preparer_chemin_sauvegarde_nom_fait_de_points():
    """'.' et '..' commencent par un point (ils désigneraient le dossier courant ou le parent) : nom vide."""
    assert app.preparer_chemin_sauvegarde(os.path.join(DOCS, "..")) == (DOCS, "")
    assert app.preparer_chemin_sauvegarde(os.path.join(DOCS, ".")) == (DOCS, "")


def test_preparer_chemin_sauvegarde_refuse_fichier_cache():
    """Un nom de fichier caché (commençant par un point, même après des espaces) est renvoyé vide."""
    assert app.preparer_chemin_sauvegarde(os.path.join(DOCS, ".foo")) == (DOCS, "")
    assert app.preparer_chemin_sauvegarde(os.path.join(DOCS, " .foo")) == (DOCS, "")


def test_preparer_chemin_sauvegarde_retire_les_points_finaux():
    """Windows retire les points finaux des noms de dossier : on les retire aussi du nom du document."""
    chemin = os.path.join(DOCS, "cours..md")
    assert app.preparer_chemin_sauvegarde(chemin) == (DOCS, "cours")
