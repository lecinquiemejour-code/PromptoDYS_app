import askGeminiPrompto as app

# --- extraire_contenu_note ---


def test_extraire_contenu_note_entre_balises():
    """Seul le contenu entre <NOTE> et </NOTE> est gardé, sans espaces autour."""
    reponse = "Préambule\n<NOTE>\n  # Ma note\n\nTexte  \n</NOTE>\nDébrief"
    assert app.extraire_contenu_note(reponse) == "# Ma note\n\nTexte"


def test_extraire_contenu_note_remplace_marqueurs_bold():
    """Les marqueurs __BOLD_n__ deviennent des séparateurs Markdown."""
    reponse = "<NOTE>Début\n__BOLD_1__\nMilieu\n__BOLD_12__\nFin</NOTE>"
    assert app.extraire_contenu_note(reponse) == "Début\n---\nMilieu\n---\nFin"


def test_extraire_contenu_note_sans_balises_renvoie_tout():
    """Sans balises, la réponse entière est utilisée, marqueurs remplacés."""
    reponse = "Texte sans balises\n__BOLD_3__\nSuite"
    assert app.extraire_contenu_note(reponse) == "Texte sans balises\n---\nSuite"


def test_extraire_contenu_note_balise_fermante_absente():
    """Une balise ouvrante seule ne suffit pas : la réponse entière est renvoyée."""
    reponse = "<NOTE>Note tronquée"
    assert app.extraire_contenu_note(reponse) == reponse


# --- extraire_debrief_correction ---


def test_extraire_debrief_apres_balise():
    """Le débrief est le texte qui suit </NOTE>."""
    reponse = "<NOTE>Note</NOTE>\n\n  Corrections : 3 fautes  \n"
    assert app.extraire_debrief_correction(reponse) == "Corrections : 3 fautes"


def test_extraire_debrief_sans_balise():
    """Sans </NOTE>, pas de débrief."""
    assert app.extraire_debrief_correction("Réponse sans balises") == ""


def test_extraire_debrief_vide_apres_balise():
    """Rien après </NOTE> : débrief vide."""
    assert app.extraire_debrief_correction("<NOTE>Note</NOTE>\n  ") == ""


# --- ajouter_note_origine ---


def test_ajouter_note_origine_ajoute_le_bloc():
    """La note d'origine est ajoutée après un séparateur et un titre."""
    resultat = app.ajouter_note_origine("Note corrigée", "Note d'origine brute")
    assert resultat == (
        "Note corrigée\n\n---\n\n"
        "### <span style=\"color: #3399ff;\">Note d'origine</span>\n\n"
        "Note d'origine brute\n"
    )


def test_ajouter_note_origine_supprime_les_images():
    """Images Markdown de l'éditeur et balises <img> sont retirées de la note d'origine."""
    original = (
        "Avant\n\n"
        "![photo](./images/photo.png){width=300px id=abc}\n\n"
        "<img src=\"./images/schema.png\" />\n\n"
        "Après"
    )
    resultat = app.ajouter_note_origine("Corrigée", original)
    assert "images/" not in resultat
    assert "<img" not in resultat
    # Les lignes vides laissées par les images sont réduites à une seule
    assert "Avant\n\nAprès" in resultat


def test_ajouter_note_origine_ne_double_pas_le_separateur():
    """Un séparateur en fin de note corrigée n'est pas doublé."""
    resultat = app.ajouter_note_origine("Note corrigée\n\n---\n", "Origine")
    assert resultat.count("---") == 1


def test_ajouter_note_origine_note_traitee_vide():
    """Une note corrigée vide est renvoyée telle quelle."""
    assert app.ajouter_note_origine("  \n", "Origine") == "  \n"


def test_ajouter_note_origine_original_que_des_images():
    """Une note d'origine faite seulement d'images n'ajoute rien."""
    original = "![a](./images/a.png)\n\n<img src=\"b.png\">"
    assert app.ajouter_note_origine("Corrigée", original) == "Corrigée"
