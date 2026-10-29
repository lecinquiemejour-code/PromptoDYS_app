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
