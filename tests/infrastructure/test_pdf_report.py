from promptodys.infrastructure import pdf_report


def test_clean_html_tags_remplace_marqueurs_bold():
    """Les marqueurs __BOLD_n__ deviennent des séparateurs Markdown."""
    assert pdf_report.clean_html_tags("a __BOLD_1__ b __BOLD_42__") == "a --- b ---"


def test_clean_html_tags_supprime_span():
    """Les balises <span> de l'éditeur (couleurs) sont retirées, le texte reste."""
    texte = '### <span style="color: #3399ff;">Titre</span>'
    assert pdf_report.clean_html_tags(texte) == "### Titre"


def test_clean_html_tags_supprime_emojis():
    """Les émojis que reportlab ne sait pas afficher sont retirés."""
    resultat = pdf_report.clean_html_tags("✅ Fait 🚀 vite 📝")
    assert not any(emoji in resultat for emoji in "✅🚀📝")
    assert "Fait" in resultat and "vite" in resultat


def test_clean_html_tags_echappe_caracteres_speciaux():
    """&, < et > sont échappés pour le mini-HTML de reportlab."""
    assert pdf_report.clean_html_tags("a < b & c > d") == "a &lt; b &amp; c &gt; d"


def test_clean_html_tags_garde_balises_autorisees():
    """<b>, <i> et <u> sont conservées."""
    texte = "<b>gras</b> <i>italique</i> <u>souligné</u>"
    assert pdf_report.clean_html_tags(texte) == texte


def _report(**overrides):
    values = {
        "original_note": "Note brute",
        "step_logs": ["ÉTAPE 1"],
        "ai_stream": "réflexion",
        "processed_note": "# Note\n**Corrigée** et *relue*\n- point",
        "correction_debrief": "Débrief",
        "token_stats": {"input": 10, "output": 20, "thinking": 5, "total": 35},
    }
    return values | overrides


def test_generate_pdf_writes_a_pdf_file(tmp_path):
    """Le Markdown du rapport donne un vrai fichier PDF."""
    pdf_path = str(tmp_path / "rapport.pdf")
    assert pdf_report.generate_pdf("# Titre\n## Section\ntexte **gras**\n```\ncode\n```", pdf_path) == pdf_path
    assert (tmp_path / "rapport.pdf").read_bytes().startswith(b"%PDF")


def test_generate_pdf_returns_none_on_error(tmp_path):
    """Un chemin impossible à écrire ne lève pas d'exception : None."""
    assert pdf_report.generate_pdf("# Titre", str(tmp_path / "absent" / "rapport.pdf")) is None


def test_save_report_creates_timestamped_pdf_in_reports_dir(tmp_path, monkeypatch):
    """Le rapport est rangé dans reports/, sous un nom horodaté."""
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr(pdf_report.config, "REPORTS_DIR", str(reports_dir))

    pdf_path = pdf_report.save_report(**_report())

    [pdf_file] = reports_dir.iterdir()
    assert pdf_path == str(pdf_file)
    assert pdf_file.name.startswith("rapport_complet_") and pdf_file.suffix == ".pdf"


def test_save_report_without_processed_note_produces_nothing(tmp_path, monkeypatch):
    """Sans note traitée, aucun rapport n'est produit."""
    reports_dir = tmp_path / "reports"
    monkeypatch.setattr(pdf_report.config, "REPORTS_DIR", str(reports_dir))

    assert pdf_report.save_report(**_report(processed_note="  ")) is None
    assert not reports_dir.exists()
