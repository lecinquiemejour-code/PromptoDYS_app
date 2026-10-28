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

---

## 4. Priorité 1 : corriger avant de restructurer

Un découpage qui déplace du code défectueux déplace aussi les bugs et brouille les diffs. Ces corrections sont décrites dans REVUE_PROJET.md ; voici où elles se trouvent aujourd'hui.

| Réf. revue | Où | Problème |
|---|---|---|
| B2 | [l. 900](../askGeminiPrompto.py#L900), [l. 916](../askGeminiPrompto.py#L916) | `return` avant le `try/finally` : le bouton reste sur « Abandonner » |
| B1 | [l. 1359](../askGeminiPrompto.py#L1359) | `style="Big.TButton"` sur un `tk.Button` : le failsafe plante |
| B3 | [l. 1199](../askGeminiPrompto.py#L1199), [l. 1398](../askGeminiPrompto.py#L1398) | Lambda qui utilise `e` après le bloc `except` |
| C2 | [l. 779](../askGeminiPrompto.py#L779), [l. 725](../askGeminiPrompto.py#L725), [l. 1406](../askGeminiPrompto.py#L1406), [l. 1723](../askGeminiPrompto.py#L1723), [l. 142](../askGeminiPrompto.py#L142) | `GeminiKey.txt`, `reports/` et `build_web/` relatifs au dossier courant |
| B6 | [l. 799](../askGeminiPrompto.py#L799) | Client Gemini sans timeout |

À noter : la correction de B1 et B2 par le découpage (priorité 3, le pipeline renvoie un résultat au lieu de piloter le bouton) rend la correction ponctuelle provisoire. On la fait quand même, car elle débloque les utilisateurs actuels sans attendre.

---

## 5. Priorité 2 : poser un filet de sécurité

**R2. Supprimer les effets de bord à l'import (M12).** Déplacer dans `main()` la création de `PROMPTO_DOCS_DIR` ([l. 207-208](../askGeminiPrompto.py#L207-L208)) et de `CHROME_PROFILE_DIR` ([l. 226](../askGeminiPrompto.py#L226)). Sans cela, aucun test ne peut importer le module sans écrire dans `Documents/`.

**R3. Tests `pytest` sur les fonctions déjà pures (D6).**
- `extraire_contenu_note` ([l. 829](../askGeminiPrompto.py#L829)) et `extraire_debrief_correction` ([l. 868](../askGeminiPrompto.py#L868)) : avec et sans balises, avec marqueurs `__BOLD_n__`.
- `ajouter_note_origine` ([l. 848](../askGeminiPrompto.py#L848)) : suppression des images, séparateur final non doublé.
- `nettoyer_html_tags` ([l. 596](../askGeminiPrompto.py#L596)) : aujourd'hui imbriquée dans `convertir_markdown_vers_paragraphes`, à sortir pour être testable.
- La logique anti-récursion de la sauvegarde ([l. 1254](../askGeminiPrompto.py#L1254)) : à extraire dans une fonction.

Ces tests protègent le cœur du produit pendant tout le découpage.

**R4. `import-linter`.** Ajouter l'outil au groupe `dev` avec un contrat de dépendances : `presentation` n'importe pas `infrastructure`, `domain` n'importe aucune autre couche. À lancer en CI avec ruff, dès la création des couches. Sans outil, la règle de dépendance dérive en quelques mois.

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

---

## 7. Priorité 4 : remplacer l'état global par des objets

Les dix `global` disparaissent au fil du découpage, mais il faut décider par quoi les remplacer.

- **Un objet d'état de l'éditeur** : ouvert ou non, `threading.Event` « prêt », document courant. Il remplace `editeur_lance`, `last_editor_activity` et `current_document_path`, et il est partagé entre la GUI et les rappels d'Eel.
- **`abandon_ia` devient un `threading.Event`**, et l'attente active du signal React (`time.sleep(0.5)` en boucle, [l. 1313](../askGeminiPrompto.py#L1313)) devient `Event.wait(timeout=30)`.
- **`PanneauControle` dans `presentation/`** : widgets et gestionnaires de boutons deviennent attributs et méthodes. Les six fonctions imbriquées de `gui_control_panel` ([l. 1143](../askGeminiPrompto.py#L1143)) se comportent déjà ainsi, par closures sur `root`, `status_label` et `btn_ia`. Il remplace `root_global`, `btn_ia_global`, `status_label_global` et `streaming_text_global`.
- **La logique métier reste en fonctions**, testables sans Tk.

**À éviter** : une classe `PromptoApp` qui regrouperait GUI, Gemini, PDF et fichiers. Ce serait le même monolithe déplacé dans une classe. L'option 3 de la revue (§9) est écartée pour cette raison, et parce qu'elle suppose de tout réécrire d'un coup. Des classes qui portent un état localisé sont en revanche bienvenues.

---

## 8. Priorité 5 : moderniser les idiomes

**R7. Journalisation.** `print`, `log_message`, `logs_complets` et `RedirectText` ([l. 88](../askGeminiPrompto.py#L88)) font quatre fois le même travail. Les remplacer par le module `logging`, avec trois handlers : un fichier avec rotation (A5), la console Tkinter via une `queue.Queue` lue par `root.after` (règle aussi M9 et M10), et un handler mémoire qui alimente le rapport PDF. Supprimer ou passer en niveau `DEBUG` les traces `🔍 DEBUG` de `save_document` ([l. 254-272](../askGeminiPrompto.py#L254-L272)) et `load_document` ([l. 398-415](../askGeminiPrompto.py#L398-L415)).

**R8. Rapport PDF.** Aujourd'hui le programme génère du Markdown ([l. 476-533](../askGeminiPrompto.py#L476-L533)) puis le reparse avec des expressions régulières ([l. 536-684](../askGeminiPrompto.py#L536-L684)) pour obtenir des éléments ReportLab. Construire directement les éléments depuis les données supprime le reparsage, la liste fixe d'émojis et le carré noir du constat M8. Avec une police Unicode (OpenDyslexic ou Lexend, déjà dans `build_web/fonts/`), les rapports deviennent lisibles par le public cible (A1).

**R9. GUI.**
- Une fonction fabrique pour les cinq `tk.Button` copiés-collés ([l. 1511-1629](../askGeminiPrompto.py#L1511-L1629), environ 120 lignes ramenées à une vingtaine).
- Hauteur de fenêtre calculée depuis l'écran (B4).

**R10. Python moderne.**
- `pathlib.Path` à la place de `os.path`.
- Annotations de type.
- `dataclass` pour les données échangées avec l'éditeur et pour le résultat du traitement.
- Imports en tête de fichier (`sys` est réimporté [l. 134](../askGeminiPrompto.py#L134), `traceback` dans deux fonctions).
- **Portabilité** : `subprocess.Popen('explorer …')` ([l. 1413](../askGeminiPrompto.py#L1413)) ne fonctionne que sous Windows ; utiliser `os.startfile`, `open` ou `xdg-open` selon la plateforme (le développement se fait aussi sous macOS).
- Mettre à jour la docstring d'en-tête, qui cite encore `build/index.html` et une « interface console » (M1).

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
