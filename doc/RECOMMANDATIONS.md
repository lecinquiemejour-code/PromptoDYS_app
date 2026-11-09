# Recommandations pour moderniser PromptoDYS

> Feuille de route pour sortir [askGeminiPrompto.py](../askGeminiPrompto.py) de son état monolithique : outillage, corrections, tests, découpage en couches, puis modernisation du code.
>
> Date : 28/10/2026. Version : 1.3.0b2, commit `9c4a6c5`. Les numéros de ligne renvoient à ce commit.
>
> Ce document **complète** [REVUE_PROJET.md](REVUE_PROJET.md) sans le recopier : les bugs et constats y restent décrits sous leurs références (B1, C2, M4…), on ne donne ici que l'ordre de traitement et la cible. **Aucune modification de code n'a été faite.** Chaque point attend un GO.

---

## Sommaire

1. [Constat](#1-constat)
2. [Tableau récapitulatif](#2-tableau-récapitulatif)
3. [Priorité 0 : installer ruff](#3-priorité-0--installer-ruff)
4. [Priorité 1 : corriger avant de restructurer](#4-priorité-1--corriger-avant-de-restructurer)
5. [Priorité 2 : poser un filet de sécurité](#5-priorité-2--poser-un-filet-de-sécurité)
6. [Priorité 3 : découper en couches](#6-priorité-3--découper-en-couches)
7. [Priorité 4 : remplacer l'état global par des objets](#7-priorité-4--remplacer-létat-global-par-des-objets)
8. [Priorité 5 : moderniser les idiomes](#8-priorité-5--moderniser-les-idiomes)
9. [Priorité 6 : pistes de fond](#9-priorité-6--pistes-de-fond)
10. [Ce qu'il ne faut pas changer](#10-ce-quil-ne-faut-pas-changer)

---

## 1. Constat

Le fichier fait 1 738 lignes et mélange cinq responsabilités : interface Tkinter, pont Eel vers l'éditeur, appel à Gemini, rapport PDF et sauvegarde des documents. Dix variables globales (`editeur_lance`, `abandon_ia`, `traitement_en_cours`, `root_global`, `btn_ia_global`, `status_label_global`, `streaming_text_global`, `current_document_path`, `last_editor_activity`, `logs_complets`) relient ces blocs entre eux.

Conséquence : l'état du bouton « Traiter la prise de note » est modifié depuis `traitement_gemini()` ([l. 1004-1013](../askGeminiPrompto.py#L1004-L1013)) et depuis trois endroits de la GUI. C'est ce qui a rendu possibles les bugs B1 et B2. Le fichier ne se teste pas non plus : l'import crée des dossiers sur le disque ([l. 207-208](../askGeminiPrompto.py#L207-L208), [l. 226](../askGeminiPrompto.py#L226)) et aucune fonction ne peut être appelée sans Tkinter ou Eel.

L'ordre ci-dessous vise à ne jamais déplacer du code non vérifié : on outille, on corrige, on teste, puis on découpe.

---

## 2. Tableau récapitulatif

| Réf. | Priorité | Recommandation | Effort | Lien revue |
|---|---|---|---|---|
| R0 | 0 | Installer ruff et corriger le bruit automatique | Faible | M3 |
| R1 | 1 | Corriger B1, B2, B3, C2, B6 dans le fichier actuel | Faible | B1, B2, B3, C2, B6 |
| R2 | 2 | Rendre le module importable sans effet de bord | Trivial | M12 |
| R3 | 2 | Écrire les tests `pytest` sur les fonctions pures | Faible | D6 |
| R4 | 2 | Ajouter `import-linter` pour la règle de dépendance | Trivial | |
| R5 | 3 | Découper en trois couches `domain`, `infrastructure`, `presentation` | Moyen | M4 |
| R6 | 4 | Remplacer les globales par des objets explicites | Moyen | M4 |
| R7 | 5 | Passer à `logging` | Moyen | M9, M10, A5 |
| R8 | 5 | Construire le PDF sans passer par du Markdown | Moyen | M8, A1 |
| R9 | 5 | Factoriser la GUI, adapter la fenêtre à l'écran | Faible | B4 |
| R10 | 5 | `pathlib`, annotations, dataclasses, portabilité | Faible | |
| R11 | 6 | Évaluer l'architecture à deux fenêtres | Variable | |

---

## 3. Priorité 0 : installer ruff

[Ruff](https://docs.astral.sh/ruff/) est un linter (`ruff check`) doublé d'un formateur (`ruff format`). Il lit le code sans l'exécuter, signale les erreurs probables et corrige automatiquement une partie des problèmes. Il remplace flake8, black, isort et pyupgrade.

**Mesure du 28/10/2026** (ruff 0.17.3, lecture seule) sur `askGeminiPrompto.py` :

| Signalement | Nombre | Intérêt |
|---|---|---|
| `F821` nom non défini | 2 | C'est le bug B3 ([l. 1199](../askGeminiPrompto.py#L1199) et [l. 1398](../askGeminiPrompto.py#L1398)) |
| `E722` `except:` nu | 4 | Attrape aussi Ctrl+C et `sys.exit()` ([l. 65, 104, 110, 117](../askGeminiPrompto.py#L65)) |
| `F541` f-string sans variable | 12 | Corrigeable automatiquement |
| Jeu élargi (`F,E,W,B,UP,SIM`) | 211, dont 119 corrigeables | Surtout des espaces en fin de ligne |

Ce que ruff **ne trouve pas** : B1, B2, C2, B6. Ce sont des bugs de logique, que seuls les tests ou la relecture détectent.

**Mise en œuvre**
1. `uv add --dev ruff`, puis une section `[tool.ruff]` dans `pyproject.toml`. Une configuration globale semble déjà active sur le poste du développeur : celle du projet rend le résultat identique pour tous et en CI.
2. `ruff check --fix` (corrections sûres seulement) dans **un commit à part**.
3. `ruff format` (environ 600 lignes de diff) dans **un autre commit dédié**, juste avant le découpage de la priorité 3. Dans le même commit qu'une correction de bug, il la rendrait illisible.
4. Option : ajouter `ruff check` au workflow [release-windows.yml](../.github/workflows/release-windows.yml).

✅ Fait :
- **Étapes 1 et 2** : ruff installé et configuré, `ruff check` ne signale plus rien.
- **Étape 3** : `ruff format` appliqué dans un commit dédié, avant le découpage. Les blocs Python des fichiers Markdown sont formatés aussi, sauf `CONTRIBUTING.md`, dont l'exemple « ❌ MAUVAIS » doit rester mal formaté.
- **Étape 4** : réalisée dans le workflow [ci.yml](../.github/workflows/ci.yml), qui vérifie `ruff check` et `ruff format --check` à chaque push.

---

## 4. Priorité 1 : corriger avant de restructurer

Un découpage qui déplace du code défectueux déplace aussi les bugs et brouille les diffs. Ces corrections sont décrites dans REVUE_PROJET.md ; voici où elles se trouvent aujourd'hui.

| Réf. revue | Où | Problème | Statut |
|---|---|---|---|
| B2 | [l. 900](../askGeminiPrompto.py#L900), [l. 916](../askGeminiPrompto.py#L916) | `return` avant le `try/finally` : le bouton reste sur « Abandonner » | ✅ Fait : l'appelant gère l'état, `traitement_gemini()` renvoie un booléen |
| B1 | [l. 1359](../askGeminiPrompto.py#L1359) | `style="Big.TButton"` sur un `tk.Button` : le failsafe plante | ✅ Fait : failsafe supprimé avec B6 |
| B3 | [l. 1199](../askGeminiPrompto.py#L1199), [l. 1398](../askGeminiPrompto.py#L1398) | Lambda qui utilise `e` après le bloc `except` | ✅ Fait : messages fixes renvoyant aux logs (traitement IA avec B6, puis `lancer_eel()`) |
| C2 | [l. 779](../askGeminiPrompto.py#L779), [l. 725](../askGeminiPrompto.py#L725), [l. 1406](../askGeminiPrompto.py#L1406), [l. 1723](../askGeminiPrompto.py#L1723), [l. 142](../askGeminiPrompto.py#L142) | `GeminiKey.txt`, `reports/` et `build_web/` relatifs au dossier courant | ✅ Fait : constante `APP_DIR` (dossier de l'exe ou du script) |
| B6 | [l. 799](../askGeminiPrompto.py#L799) | Client Gemini sans timeout | ✅ Fait autrement : pas de timeout (durée de réponse imprévisible), abandon immédiat par jeton d'annulation |

Les numéros de ligne sont ceux de la rédaction et ont bougé depuis.

À noter : la correction de B1 et B2 par le découpage (priorité 3, le pipeline renvoie un résultat au lieu de piloter le bouton) rend la correction ponctuelle provisoire. On la fait quand même, car elle débloque les utilisateurs actuels sans attendre.

---

## 5. Priorité 2 : poser un filet de sécurité

**R2. Supprimer les effets de bord à l'import (M12).** Déplacer dans `main()` la création de `PROMPTO_DOCS_DIR` ([l. 207-208](../askGeminiPrompto.py#L207-L208)) et de `CHROME_PROFILE_DIR` ([l. 226](../askGeminiPrompto.py#L226)). Sans cela, aucun test ne peut importer le module sans écrire dans `Documents/`.

✅ Fait : les deux dossiers sont créés dans `main()`. L'appel Windows `SetProcessDpiAwareness`, autre effet de bord à l'import, y a aussi été déplacé (avant la création de la fenêtre Tk). pytest est installé et `tests/test_import.py` vérifie que l'import ne crée aucun dossier.

**R3. Tests `pytest` sur les fonctions déjà pures (D6).**
- `extraire_contenu_note` ([l. 829](../askGeminiPrompto.py#L829)) et `extraire_debrief_correction` ([l. 868](../askGeminiPrompto.py#L868)) : avec et sans balises, avec marqueurs `__BOLD_n__`.
- `ajouter_note_origine` ([l. 848](../askGeminiPrompto.py#L848)) : suppression des images, séparateur final non doublé.
- `nettoyer_html_tags` ([l. 596](../askGeminiPrompto.py#L596)) : aujourd'hui imbriquée dans `convertir_markdown_vers_paragraphes`, à sortir pour être testable.
- La logique anti-récursion de la sauvegarde ([l. 1254](../askGeminiPrompto.py#L1254)) : à extraire dans une fonction.

Ces tests protègent le cœur du produit pendant tout le découpage.

✅ Fait : 22 tests dans `tests/test_note.py`, `tests/test_rapport.py` et `tests/test_sauvegarde.py`. `nettoyer_html_tags` est passée au niveau du module ; l'assainissement du nom et l'anti-récursion sont extraits dans `preparer_chemin_sauvegarde()`. `tests/test_import.py` vide le registre d'Eel le temps de son réimport, sinon Eel refuse d'exposer deux fois les mêmes fonctions. Les tests ont fait apparaître le bug B8 (nom de document vide), à corriger dans une branche dédiée.

**R4. `import-linter`.** Ajouter l'outil au groupe `dev` avec un contrat de dépendances : `presentation` n'importe pas `infrastructure`, `domain` n'importe aucune autre couche. À lancer en CI avec ruff, dès la création des couches. Sans outil, la règle de dépendance dérive en quelques mois.

✅ Fait : import-linter est dans le groupe `dev`, avec trois contrats `forbidden` dans `[tool.importlinter]` de `pyproject.toml` :
- `domain` n'importe ni les autres couches, ni `tkinter`, `sv_ttk`, `eel`, `google` ou `reportlab` ;
- `presentation` n'importe ni `infrastructure`, ni `eel`, `google` ou `reportlab` ;
- `infrastructure` n'importe pas `presentation`.

`include_external_packages` permet d'interdire les bibliothèques, `tkinter` compris : une violation volontaire de chacune est bien détectée. Les paquets `infrastructure/` et `presentation/` existent déjà, vides, pour que leurs contrats s'appliquent. La CI lance `uv run lint-imports` après ruff, à chaque push.

---

## 6. Priorité 3 : découper en couches

Un simple découpage par fichiers (la proposition M4 de la revue) range le code mais n'interdit aucune dépendance : l'interface pourrait continuer à importer `reportlab` ou `eel`. La cible est donc un découpage **par couches avec une règle de dépendance**, dans un paquet `promptodys/`.

### Les trois couches

```
promptodys/
  domain/          règles pures, cas d'usage, interfaces (Protocol)
  infrastructure/  Gemini, Eel, disque, PDF, configuration
  presentation/    PanneauControle (Tkinter)
  __main__.py      python -m promptodys
askGeminiPrompto.py   mince enveloppe qui appelle main()
```

| Couche | Contenu | Interdit |
|---|---|---|
| `domain/` | Extraction `<NOTE>`, note d'origine, contenu du rapport, assainissement des noms de fichiers, anti-récursion. Cas d'usage `traiter_note()`, `sauvegarder()`, `ouvrir()` qui renvoient un `ResultatTraitement` (dataclass). Interfaces `Editeur` et `ModeleIA` | Tout import de Tk, Eel, genai, reportlab, ou des autres couches |
| `infrastructure/` | `GeminiClient`, `EelEditeur`, `DisqueDocuments`, `RapportPdf`, configuration (chemins, clé API). Implémente les interfaces du domaine | Importer `presentation` |
| `presentation/` | Panneau de contrôle Tkinter | Importer `genai`, `reportlab`, `eel` ou `infrastructure` |

**Règle de dépendance :** `presentation` → `domain` ← `infrastructure`. Seul `main()` assemble les couches.

### Pourquoi « infrastructure » et pas « data »

Le trio habituel `domain / data / presentation` convient, mais « data » évoque des dépôts de données. Ici l'appel à Gemini, la génération du PDF et le pont vers Chrome n'en sont pas. Le rôle est le même, le nom est plus exact.

### Lien avec les architectures de référence

Cette organisation suit l'**architecture hexagonale** : `domain/` déclare deux ports sortants (`Editeur`, `ModeleIA`), `infrastructure/` contient les adaptateurs sortants (Eel, Gemini, disque, PDF) et `presentation/` l'adaptateur entrant. La Clean Architecture ajoute une séparation entre entités et cas d'usage ; elle n'est pas reprise ici, elle ajouterait une couche sans bénéfice sur 1 700 lignes.

### Ce que ça apporte

- **B1 et B2 disparaissent par construction** : `traiter_note()` renvoie un résultat, la GUI décide seule de l'état du bouton.
- **Des tests sans Tkinter, Chrome ni réseau**, avec un faux éditeur et un faux Gemini.
- **Un front-end remplaçable** : une autre interface (professeurs, export DOCX annoncés au CHANGELOG) réutilise `domain/` telle quelle.

### Règles de conception

- **Deux `Protocol` seulement**, pas de hiérarchies de classes ni d'injection de dépendances automatique.
- **Une seule langue** pour les noms de modules, classes et fonctions. Le code mélange aujourd'hui `save_document` et `sauvegarder_rapport`. Les noms `domain`, `infrastructure`, `presentation` supposent l'anglais ; messages et commentaires restent en français.
- **Point d'entrée** : `promptodys/__main__.py`. `askGeminiPrompto.py` reste comme mince enveloppe, car [PromptoDYS.spec](../PromptoDYS.spec), le workflow de release et les docs le citent. Pas de layout `src/` : `pyproject.toml` déclare `package = false`, c'est une application et non une bibliothèque.
- **Threads** : le cas d'usage tourne dans un thread, pas Tkinter. Les événements passent par une `queue.Queue` lue par `root.after`, jamais par des appels directs à des widgets.
- **Rester léger** : un seul niveau de sous-dossiers. Si cette structure paraît lourde, la variante minimale est trois modules plats (`domain.py`, `infrastructure.py`, `presentation.py`) à scinder plus tard.

### Ordre de migration

Un commit par couche, tests et `import-linter` relancés à chaque étape :

1. **`domain/`**, règles pures d'abord (R3 sert de filet), puis les cas d'usage. Factoriser au passage la regex `__BOLD_n__` dupliquée ([l. 599-602](../askGeminiPrompto.py#L599-L602) et [l. 836-844](../askGeminiPrompto.py#L836-L844)).
2. **`infrastructure/`** : configuration (`BASE_DIR`, qui règle C2), documents (avec `basename` sur le nom d'image, [l. 307](../askGeminiPrompto.py#L307), constat M6), PDF, Gemini (timeout, B6), pont Eel.
3. **`presentation/`** : le panneau de contrôle, puis réduction de `askGeminiPrompto.py` à l'enveloppe de `main()`.

**Points d'attention** : vérifier que [PromptoDYS.spec](../PromptoDYS.spec) détecte bien le paquet (rebuild par la CI), mettre à jour [ARCHITECTURE.md](ARCHITECTURE.md) (§2, §4, §7) et [WORKFLOW_GEMINI.md](WORKFLOW_GEMINI.md).

✅ Étape 1 (`domain/`) faite. `promptodys/domain/` contient :
- `note.py` : prompt, extraction de la note et du débrief, note d'origine, regex `__BOLD_n__` factorisée dans `replace_bold_markers()` ;
- `report.py` : contenu Markdown du rapport ;
- `documents.py` : chemin de sauvegarde, cas d'usage `save_document()` et `open_document()` ;
- `processing.py` : cas d'usage `process_note()`, qui renvoie un `ProcessingResult` (`COMPLETED`, `FAILED` ou `CANCELLED`) ;
- `ports.py` : les ports et les données qu'ils échangent.

Les adaptateurs ont rejoint `infrastructure/` à l'étape 2 (voir plus bas). Le rapport PDF produit après le découpage a été comparé à un rapport d'avant : structure et contenu identiques, hors numérotation des étapes.

Écarts aux règles ci-dessus, décidés pendant la migration :
- **Trois ports au lieu de deux** : `Editor`, `AIModel` et `DocumentStore`. Sans `DocumentStore`, sauvegarder et ouvrir n'auraient pas pu devenir des cas d'usage testables.
- **`Protocol` hérités explicitement** : `class EelEditor(ports.Editor)`. Le lien se lit dans le code. Comme les méthodes des ports ne sont pas marquées `@abstractmethod`, rien n'oblige un adaptateur à toutes les redéfinir : une méthode oubliée hérite du corps vide du Protocol (`...`) et renvoie `None` au lieu de lever une erreur. Les faux des tests n'héritent pas des ports. Depuis l'étape 2, pyright vérifie les adaptateurs (voir R10) : une méthode à la signature incompatible avec son port est signalée sur la classe. Une méthode oubliée n'est signalée qu'à l'instanciation (« Cannot instantiate abstract class ») : depuis l'étape 3, les adaptateurs sont instanciés dans `promptodys/app.py`, dans le périmètre de pyright, et ce second contrôle joue aussi.
- **Journalisation du domaine avec `logging`** (`_logger = logging.getLogger(__name__)`), plutôt qu'une fonction de log injectée. Un handler provisoire, `LogMessageHandler`, renvoie ces messages vers `log_message` jusqu'à R7.
- **Imports de modules** : `from promptodys.domain import note`, puis `note.extract_note_content(...)`.
- **Étapes renumérotées** : 1 client et configuration, 2 modèle de prompt, 3 lecture de l'éditeur, 4 prompt, 5 flux, 6 extraction, 7 injection, 8 jetons, 9 PDF. Les étapes 1, 2 et 9 dépendent de l'infrastructure et restent dans `traitement_gemini()`.

La règle des noms anglais s'applique au nouveau code. Le code encore dans `askGeminiPrompto.py` garde ses noms français jusqu'à son déplacement. Depuis l'étape 3, tout le code est dans le paquet et suit cette règle.

✅ Étape 2 (`infrastructure/`) faite, un commit par module. `promptodys/infrastructure/` contient :
- `config.py` : constantes `GEMINI_MODEL` et `GEMINI_THINKING_LEVEL` (toujours en tête de fichier), chemins (`APP_DIR`, `REPORTS_DIR`, `PROMPTO_DOCS_DIR`, `CHROME_PROFILE_DIR`, `RESOURCES_DIR`), `EEL_PORT`, lecture de la clé API et du modèle de prompt, recherche de `build_web/`. Aucun dossier n'est créé à l'import (M12) ;
- `disk_document_store.py` : `DiskDocumentStore`, avec le correctif M6 (nom d'image réduit à son dernier composant) ;
- `pdf_report.py` : rapport PDF ReportLab, déplacé sans refonte (celle-ci relève de R8). Les éléments ReportLab produits ont été comparés à ceux d'avant le déplacement : identiques ;
- `gemini_model.py` : `GeminiModel` et création du client ;
- `eel_editor.py` : `EelEditor`, ouverture et fermeture de la fenêtre de l'éditeur (`init()`, `start()`, `close()`), événements de React, disponibilité du port. `askGeminiPrompto.py` n'importe plus `eel`, `google.genai` ni `reportlab`.

Écarts aux règles ci-dessus, décidés pendant la migration :
- **Un module porte le nom de son adaptateur** (`disk_document_store.py` pour `DiskDocumentStore`, `gemini_model.py` pour `GeminiModel`) ; `config.py` et `pdf_report.py`, qui n'implémentent pas de port, portent le nom de leur rôle. Cela évite aussi un second module `documents`, déjà pris par le domaine.
- **Tout ce qui touche à Eel est dans `eel_editor.py`**, y compris `eel.init`, `eel.start` et `closeEditor`, que l'ordre de migration ne citait pas : sans cela, `presentation` n'aurait pas pu se passer d'`eel` à l'étape 3.
- **Événements de React par fonctions de rappel** : `on_editor_open` et `on_editor_close` gardent leur nom et restent synchrones, mais ne touchent plus l'interface. Elles appellent les fonctions enregistrées par `set_event_handlers()`, que `main()` relie à `_editeur_ouvert()` et `_editeur_ferme()`. Depuis l'étape 3, ce sont les méthodes `on_editor_open()` et `on_editor_close()` du panneau.
- **Journalisation** : les modules d'infrastructure utilisent `logging`, comme le domaine, pour les messages qui allaient dans `log_message`. Les `print()` de `EelEditor` et `DiskDocumentStore` (traces détaillées et `🔍 DEBUG`) restent des `print()` jusqu'à R7, pour ne pas les faire entrer dans le rapport PDF.
- **La balise `[TEXTE]` est déclarée une seule fois**, dans le domaine (`note.TEXT_PLACEHOLDER`) : `build_prompt()` la remplace, `config.read_prompt_template()` vérifie sa présence.

Le build PyInstaller embarque bien les modules du sous-paquet, sans modification de [PromptoDYS.spec](../PromptoDYS.spec). Pour l'étape 3 : l'icône et le logo du panneau sont cherchés avec `os.path.dirname(__file__)`, à remplacer par `config.RESOURCES_DIR` transmis par `main()`, puisque `presentation` n'importe pas `infrastructure`.

✅ Étape 3 (`presentation/`) faite. Le paquet est complet :
- `presentation/control_panel.py` : `ControlPanel` (l'ancienne fonction `gui_control_panel()`), `EditorWindow` et `RedirectText`. Le panneau reçoit toutes ses dépendances de `main()` : l'éditeur et le `DocumentStore` (ports du domaine), la fenêtre de l'éditeur, le traitement IA, les dossiers et le chemin de l'icône. Il n'importe que `tkinter`, `sv_ttk` et le domaine ;
- `app.py` : module d'assemblage, avec `main()`, `run_processing()` (étapes 1, 2 et 9 du traitement IA, autour de `process_note()`) et la journalisation provisoire (`report_logs`, `log_message`, `LogMessageHandler`, `configure_logger`) ;
- `__main__.py` : lancement par `python -m promptodys` ;
- `askGeminiPrompto.py` : enveloppe de 15 lignes, toujours citée par [PromptoDYS.spec](../PromptoDYS.spec), la release et les docs.

Aucun test ne crée de fenêtre Tk : `tests/presentation/test_control_panel.py` a été supprimé, parce que sous Windows (CI, Python 3.14.10) créer plusieurs Tk dans un même processus fait échouer au hasard le `source` des fichiers Tcl de sv_ttk (« couldn't read file », puis « Theme sun-valley-light already exists » quand les interpréteurs sont gardés en vie). L'application n'est pas concernée : elle ne crée qu'un Tk. La logique du panneau a ensuite été sortie de `ControlPanel` dans `PanelController` (voir les écarts ci-dessous) : la coordination (double clic, port occupé, attente du signal de React, sauvegarde, abandon du traitement, fermeture) est testée sans Tk dans `tests/presentation/test_panel_controller.py`. Seule la vue Tk reste sans tests automatisés. L'icône est passée par `main()` (`icon_path`, construit depuis `config.RESOURCES_DIR`) ; un build PyInstaller l'a bien chargée depuis la copie embarquée.

Écarts aux règles ci-dessus, décidés pendant la migration :
- **Un module d'assemblage `app.py` en plus de `__main__.py`** : `main()` et `run_processing()` doivent pouvoir être importés par les tests, ce que `__main__.py` ne permet pas proprement. `__main__.py` ne fait qu'appeler `main()`. `app.py` est hors des trois couches, et un quatrième contrat import-linter interdit à toute couche de l'importer.
- **Un `Protocol` de plus, `EditorWindow`, déclaré dans la présentation** : ouvrir et fermer la fenêtre de l'éditeur est un besoin du panneau, pas du domaine. `EelWindow` (dans `eel_editor.py`) le satisfait sans en hériter, puisque l'infrastructure n'importe pas la présentation ; pyright vérifie la compatibilité à l'appel de `PanelController(...)` dans `main()`. Le traitement est passé comme un simple `Callable` : `functools.partial(run_processing, editor)`.
- **R6 commencée** : les globales deviennent des attributs de `ControlPanel` (`_editor_open`, `_editor_starting`, `_closing`, `_cancel_event`, `_current_document_path`, `_last_editor_activity`). R6 a ensuite regroupé l'état de l'éditeur dans `EditorState` (voir priorité 4).
- **R7 commencée** : le panneau journalise avec `logging`, et `log_message()` ne sert plus que dans `app.py`. Tous les `root.after` venant d'autres threads passent par `PanelController._in_ui_thread()` (qui appelle `after()` de la vue), seul endroit à changer pour la file d'attente de R7. La console est vidée par le panneau au lancement d'un traitement, par la même file `root.after` que les logs, et non plus par le traitement.
- **Contrôleur et vue séparés** : `PanelController` (`panel_controller.py`) contient la logique du panneau : réaction aux boutons et aux signaux de React, threads, `EditorState`, `_closing`, `_cancel_event`, constantes de délai. `ControlPanel` n'est plus que la vue Tk : il construit la fenêtre et satisfait le Protocol `PanelView` (`show_status`, `set_processing`, `clear_console`, `refresh`, popups, dialogues de fichiers, `after`, `quit`), que pyright vérifie. Le code a été déplacé sans changer de comportement : mêmes textes, mêmes popups, mêmes threads. Un contrat import-linter interdit à `panel_controller` et `editor_state` d'importer `tkinter` ou `sv_ttk`. `main()` crée la vue, puis le contrôleur, à qui il passe la vue et les dépendances (éditeur, `DocumentStore`, fenêtre de l'éditeur, traitement) ; il donne le contrôleur à la vue avec `set_controller()`, qui ne fait que garder la référence, et enregistre `PanelController.on_editor_open()` et `on_editor_close()` auprès d'Eel. Les boutons appellent des méthodes privées de la vue (`_on_open_editor()`...), qui lisent le contrôleur au moment du clic, ce qui est sûr : aucun événement Tk n'est traité avant `run()`, qui vérifie que le contrôleur a été donné. La vue ne reçoit donc plus de dépendances qu'elle ne fait que transmettre, ni de méthodes qui ne font que relayer les signaux de React.
- **Construction et boucle séparées** : `ControlPanel(...)` construit la fenêtre, cachée ; `run()` redirige stdout et stderr, affiche la fenêtre et lance la boucle.
- **Réglage DPI** : `if sys.platform == "win32"` au lieu d'un `try/except ImportError`, ce que pyright comprend.

Les traces `🔍 DEBUG` du bouton « Sauvegarder » citent encore d'anciens noms de variables (`btn_sauvegarder`, `editeur_lance`) : elles seront supprimées ou passées au niveau `DEBUG` avec R7.

---

## 7. Priorité 4 : remplacer l'état global par des objets

Les dix `global` disparaissent au fil du découpage, mais il faut décider par quoi les remplacer.

- ✅ **Un objet d'état de l'éditeur** : ouvert ou non, `threading.Event` « prêt », document courant. Il remplace `editeur_lance`, `last_editor_activity` et `current_document_path`, et il est partagé entre la GUI et les rappels d'Eel. Fait : classe `EditorState` dans `promptodys/presentation/editor_state.py`, créée par `PanelController` (`_editor_state`). Elle remplace les attributs `_editor_open`, `_editor_starting`, `_last_editor_activity` et `_current_document_path` du panneau. Transitions : `start_requested()` (clic sur « Ouvrir l'éditeur »), `opened()` et `closed()` (signaux de React), `launch_ended()` (retour ou échec de `editor_window.start()`, port pris). Elle n'importe que `threading` et se teste sans Tk (`tests/presentation/test_editor_state.py`).
  - **Un seul `Event` pour « ouvert » et « prêt »** : `_editor_open` et `_last_editor_activity` ne passaient à « ouvert » que dans `on_editor_open()`, et le timestamp n'était jamais lu comme une heure. Ils ne revenaient pas à zéro aux mêmes endroits : si Chrome se fermait sans que React envoie `on_editor_close` (plantage, `beforeunload` perdu), `_launch_editor` remettait `_editor_open` à faux mais laissait `_last_editor_activity` rempli. Au clic suivant sur « Ouvrir », le document partait vers un éditeur pas encore monté (« ❌ Erreur d'ouverture »). Avec un seul `Event`, la fin du lancement règle aussi ce cas ; un test du contrôleur le vérifie.
  - **Modifié par le thread de l'interface seulement** : c'est un état de l'interface. Les signaux de React (threads d'Eel), les fins de lancement et les fins de sauvegarde ou d'ouverture (`document_path`) lui parviennent par `_in_ui_thread()`, avec la mise à jour du statut correspondante. `EditorState` retient le thread qui l'a créé et lève `RuntimeError` si un autre thread le modifie. Les autres threads peuvent seulement attendre l'ouverture (`wait_until_open`, un `Event.wait`). Un verrou n'aurait pas suffi : il rend chaque écriture atomique, mais ne remet pas dans l'ordre des écritures venues de threads différents.
  - **Jeton de lancement**, comme le jeton d'annulation du traitement IA : `start_requested()` renvoie un jeton, que le thread de lancement rend à `launch_ended()`. La fin d'un lancement remplacé est ignorée (état, statut et popup). Le cas, antérieur à R6 : après la fermeture de Chrome, React signale `on_editor_close` tout de suite, mais Eel ne rend la main qu'au bout de `shutdown_delay` (1 s). Si l'élève relançait l'éditeur entre-temps, la fin de l'ancien lancement remettait à faux le drapeau « en cours d'ouverture » du nouveau ; un clic de plus lançait un second éditeur, qui trouvait le port pris et marquait fermé le vrai éditeur. Testé dans le contrôleur et dans `EditorState`.
  - **Le document courant survit à la fermeture** de l'éditeur : le dialogue de sauvegarde reste pré-rempli, comme avant.
  - **`_closing` et `_cancel_event` restent hors d'`EditorState`**, dans `PanelController` : ils concernent la fermeture de l'application et le traitement IA.
- ✅ **`abandon_ia` devient un `threading.Event`** : fait avec B6. `abandon_ia` et `traitement_en_cours` sont remplacées par un jeton d'annulation propre à chaque traitement, et par `annulation_en_cours`, le jeton du traitement en cours. L'attente active du signal React (`time.sleep(0.5)` en boucle, [l. 1313](../askGeminiPrompto.py#L1313)) est devenue `EditorState.wait_until_open(EDITOR_READY_TIMEOUT_S)`, soit `Event.wait(timeout=30)`. Les délais (`EDITOR_READY_TIMEOUT_S`, `REACT_SETTLE_DELAY_S` = 1,5 s après le signal) sont des constantes de `panel_controller.py`, que les tests réduisent. L'attente de la fermeture de l'éditeur au moment de quitter reste un sondage par `after()` de la vue (`root.after`) : elle tourne sur le thread de l'interface, qu'un `Event.wait` bloquerait.
- ✅ **`PanneauControle` dans `presentation/`** (fait avec R5 étape 3, sous le nom `ControlPanel`) : widgets et gestionnaires de boutons deviennent attributs et méthodes. Les six fonctions imbriquées de `gui_control_panel` ([l. 1143](../askGeminiPrompto.py#L1143)) se comportent déjà ainsi, par closures sur `root`, `status_label` et `btn_ia`. Il remplace `root_global`, `status_label_global` et `streaming_text_global` (`btn_ia_global` a déjà disparu avec B2). `annulation_en_cours`, utilisée uniquement par le thread principal, y devient un attribut.
- **La logique métier reste en fonctions**, testables sans Tk.

**À éviter** : une classe `PromptoApp` qui regrouperait GUI, Gemini, PDF et fichiers. Ce serait le même monolithe déplacé dans une classe. L'option 3 de la revue (§9) est écartée pour cette raison, et parce qu'elle suppose de tout réécrire d'un coup. Des classes qui portent un état localisé sont en revanche bienvenues.

---

## 8. Priorité 5 : moderniser les idiomes

**R7. Journalisation.** `print`, `log_message`, `logs_complets` et `RedirectText` ([l. 88](../askGeminiPrompto.py#L88)) font quatre fois le même travail. Depuis R5 étape 3, `log_message` et `report_logs` (l'ancien `logs_complets`) sont dans `promptodys/app.py`, `RedirectText` dans `promptodys/presentation/control_panel.py`, et les appels à `root.after` venant d'autres threads passent tous par `PanelController._in_ui_thread()`. Les remplacer par le module `logging`, avec trois handlers : un fichier avec rotation (A5), la console Tkinter via une `queue.Queue` lue par `root.after` (règle aussi M9 et M10), et un handler mémoire qui alimente le rapport PDF. Supprimer ou passer en niveau `DEBUG` les traces `🔍 DEBUG` de `save_document` ([l. 254-272](../askGeminiPrompto.py#L254-L272)) et `load_document` ([l. 398-415](../askGeminiPrompto.py#L398-L415)).

**R8. Rapport PDF.** Aujourd'hui le programme génère du Markdown ([l. 476-533](../askGeminiPrompto.py#L476-L533)) puis le reparse avec des expressions régulières ([l. 536-684](../askGeminiPrompto.py#L536-L684)) pour obtenir des éléments ReportLab. Construire directement les éléments depuis les données supprime le reparsage, la liste fixe d'émojis et le carré noir du constat M8. Avec une police Unicode (OpenDyslexic ou Lexend, déjà dans `build_web/fonts/`), les rapports deviennent lisibles par le public cible (A1).

**R9. GUI.**
- Une fonction fabrique pour les cinq `tk.Button` copiés-collés ([l. 1511-1629](../askGeminiPrompto.py#L1511-L1629), environ 120 lignes ramenées à une vingtaine).
- Hauteur de fenêtre calculée depuis l'écran (B4).

**R10. Python moderne.**
- `pathlib.Path` à la place de `os.path`.
- Annotations de type. pyright est en place (`[tool.pyright]` de `pyproject.toml`, lancé en CI) : mode strict sur `promptodys/domain/`, standard sur le reste du paquet (`infrastructure/`, `presentation/`, `app.py`). Restent hors périmètre `askGeminiPrompto.py`, devenu une simple enveloppe, et les tests.
- `dataclass` pour les données échangées avec l'éditeur et pour le résultat du traitement.
- Imports en tête de fichier (`sys` est réimporté [l. 134](../askGeminiPrompto.py#L134), `traceback` dans deux fonctions).
- **Portabilité** : `subprocess.Popen('explorer …')` ([l. 1413](../askGeminiPrompto.py#L1413)) ne fonctionne que sous Windows ; utiliser `os.startfile`, `open` ou `xdg-open` selon la plateforme (le développement se fait aussi sous macOS).
- ✅ Mettre à jour la docstring d'en-tête, qui cite encore `build/index.html` et une « interface console » (M1) : réécrite avec R5 étape 3.

---

## 9. Priorité 6 : pistes de fond

À évaluer plus tard, avant toute nouvelle grosse fonctionnalité. Ce sont des pistes, sans conclusion.

**R11. Deux fenêtres pour un seul outil.** L'élève manipule un panneau Tkinter et une fenêtre Chrome qui affiche l'éditeur. Déplacer les boutons dans l'éditeur React, ou remplacer Eel par une autre solution (par exemple pywebview), supprimerait cette séparation. La couche `domain/` isolée par la priorité 3 rend ce changement possible sans toucher aux règles métier.

---

## 10. Ce qu'il ne faut pas changer

Voir REVUE_PROJET.md [§8](REVUE_PROJET.md#8-ce-qui-est-bien-fait). À préserver pendant la migration :

- les étapes numérotées du traitement IA et leurs logs explicites ;
- la convention de sauvegarde « façon Arduino » (dossier du nom du document, `.md` et `images/`) ;
- l'attente du vrai signal React (`on_editor_open`) avant de charger un document ;
- les constantes `GEMINI_MODEL` et `GEMINI_THINKING_LEVEL` en tête de configuration ;
- les fonctions Eel exposées **synchrones** (voir [ARCHITECTURE.md](ARCHITECTURE.md#règle-technique-importante)).
