import importlib
import os
import sys

import eel


def test_import_ne_cree_aucun_dossier(monkeypatch):
    """Importer le module ne doit rien écrire sur le disque (constat M12)."""
    dossiers_crees = []
    monkeypatch.setattr(os, "makedirs", lambda chemin, *args, **kwargs: dossiers_crees.append(chemin))
    # Forcer un vrai import, même si un autre test a déjà chargé le module
    monkeypatch.delitem(sys.modules, "askGeminiPrompto", raising=False)
    # Eel refuse d'exposer deux fois la même fonction : registre vierge le temps du réimport
    monkeypatch.setattr(eel, "_exposed_functions", {})

    importlib.import_module("askGeminiPrompto")

    # Seuls nos dossiers comptent : une bibliothèque tierce peut créer les siens à l'import
    assert [chemin for chemin in dossiers_crees if "PromptoDYS" in str(chemin)] == []


def test_domain_import_creates_no_folder(monkeypatch):
    """Importer la couche domaine ne doit rien écrire sur le disque."""
    dossiers_crees = []
    monkeypatch.setattr(os, "makedirs", lambda chemin, *args, **kwargs: dossiers_crees.append(chemin))
    for nom in [nom for nom in sys.modules if nom.startswith("promptodys")]:
        monkeypatch.delitem(sys.modules, nom)

    for module in ("note", "report", "documents", "ports", "processing"):
        importlib.import_module(f"promptodys.domain.{module}")

    assert dossiers_crees == []


def test_infrastructure_import_creates_no_folder(monkeypatch):
    """Importer la couche infrastructure ne doit rien écrire sur le disque (constat M12)."""
    dossiers_crees = []
    monkeypatch.setattr(os, "makedirs", lambda chemin, *args, **kwargs: dossiers_crees.append(chemin))
    for nom in [nom for nom in sys.modules if nom.startswith("promptodys")]:
        monkeypatch.delitem(sys.modules, nom)

    for module in ("config", "disk_document_store", "pdf_report", "gemini_model"):
        importlib.import_module(f"promptodys.infrastructure.{module}")

    assert [chemin for chemin in dossiers_crees if "PromptoDYS" in str(chemin)] == []
