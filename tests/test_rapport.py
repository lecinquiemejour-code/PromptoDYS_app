import askGeminiPrompto as app


def test_nettoyer_html_tags_remplace_marqueurs_bold():
    """Les marqueurs __BOLD_n__ deviennent des séparateurs Markdown."""
    assert app.nettoyer_html_tags("a __BOLD_1__ b __BOLD_42__") == "a --- b ---"


def test_nettoyer_html_tags_supprime_span():
    """Les balises <span> de l'éditeur (couleurs) sont retirées, le texte reste."""
    texte = "### <span style=\"color: #3399ff;\">Titre</span>"
    assert app.nettoyer_html_tags(texte) == "### Titre"


def test_nettoyer_html_tags_supprime_emojis():
    """Les émojis que reportlab ne sait pas afficher sont retirés."""
    resultat = app.nettoyer_html_tags("✅ Fait 🚀 vite 📝")
    assert not any(emoji in resultat for emoji in "✅🚀📝")
    assert "Fait" in resultat and "vite" in resultat


def test_nettoyer_html_tags_echappe_caracteres_speciaux():
    """&, < et > sont échappés pour le mini-HTML de reportlab."""
    assert app.nettoyer_html_tags("a < b & c > d") == "a &lt; b &amp; c &gt; d"


def test_nettoyer_html_tags_garde_balises_autorisees():
    """<b>, <i> et <u> sont conservées."""
    texte = "<b>gras</b> <i>italique</i> <u>souligné</u>"
    assert app.nettoyer_html_tags(texte) == texte
