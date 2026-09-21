# Développement du Backend MeteoGPT

## Introduction

Après la phase expérimentale réalisée dans le notebook, le projet MeteoGPT entre
dans une nouvelle étape : la transformation des composants intelligents validés
en une application backend structurée.

Le notebook a permis de concevoir, expérimenter et valider les principaux
composants du système :

- l'Agent conversationnel basé sur LangGraph ;
- le Retriever hybride combinant Dense Retrieval, BM25, Reciprocal Rank Fusion
  et filtrage par métadonnées ;
- le module de génération RAG ;
- les mécanismes de prévention des hallucinations ;
- le traitement audio ;
- le pipeline d'actualisation des données ANACIM ;
- l'intégration avec Qdrant ;
- les tests fonctionnels et les évaluations de performance.

La phase backend ne consiste donc pas à reconstruire ces composants.

Son objectif est de les intégrer dans une architecture applicative propre afin
de pouvoir les exposer à travers une API et, par la suite, les connecter à
WhatsApp Cloud API.

Le développement du backend est réalisé de manière incrémentale.

Chaque étape est identifiée par une phase `B`.

La démarche retenue est la suivante :

```text
B0  → Initialisation Git
B1  → Environnement de développement
B2  → Configuration applicative
B3  → FastAPI minimal
B4  → Intégration du pipeline RAG
B5  → Gestion des erreurs, logs et monitoring
B6  → Intégration du pipeline d'actualisation ANACIM
B7  → Intégration audio
B8  → WhatsApp Cloud API
B9  → Tests backend
B10 → Finalisation
```

Chaque phase suit le même principe :

```text
Objectif
   ↓
Implémentation
   ↓
Tests
   ↓
Validation
   ↓
Commit Git
   ↓
Fusion dans develop
```

Cette organisation permet de conserver un historique clair du développement et
d'éviter d'introduire plusieurs modifications importantes simultanément.

---

# B0 — Initialisation et organisation du dépôt Git

## B0.1 Objectif

La première étape consiste à créer un dépôt Git dédié au backend.

Le dépôt backend est volontairement séparé du dépôt utilisé pour le notebook
expérimental.

Cette séparation permet de distinguer clairement deux environnements.

Le premier correspond à la phase expérimentale :

```text
MeteoGPT
│
├── Notebook
├── expérimentation RAG
├── tests
├── évaluations
└── résultats expérimentaux
```

Le second correspond à la phase applicative :

```text
MeteoGPT_Backend
│
├── backend FastAPI
├── configuration
├── services
├── API
├── intégration RAG
├── WhatsApp Cloud API
└── tests applicatifs
```

Le nouveau dépôt GitHub a donc été créé sous le nom :

```text
MeteoGPT_Backend
```

Ce dépôt devient la référence pour toute la suite du développement applicatif.

---

## B0.2 Organisation Git retenue

Une stratégie de branches simple a été retenue afin de structurer le
développement.

La branche :

```text
main
```

représente les versions stables du projet.

La branche :

```text
develop
```

est utilisée comme branche d'intégration.

Chaque nouvelle fonctionnalité importante est développée dans une branche
spécifique :

```text
feature/...
```

Les corrections ponctuelles sont réalisées dans des branches :

```text
fix/...
```

L'organisation générale est donc :

```text
main
 │
 └── develop
      │
      ├── feature/b1-environment
      ├── feature/b2-configuration
      ├── feature/b3-fastapi-core
      ├── feature/b4-chat-rag
      ├── feature/b5-observability
      ├── feature/b6-anacim-update
      ├── feature/b7-audio
      ├── feature/b8-whatsapp-cloud
      ├── feature/b9-tests
      └── feature/b10-finalization
```

Cette stratégie évite de développer directement sur `main` ou `develop`.

Elle permet également d'isoler chaque phase et de ne la fusionner qu'après sa
validation.

---

## B0.3 Initialisation du dépôt

Le dépôt a d'abord été créé sur GitHub.

Il a ensuite été récupéré localement afin de travailler depuis VS Code.

La branche principale est :

```text
main
```

Une branche d'intégration a ensuite été créée :

```text
develop
```

Le fonctionnement retenu est :

```text
feature
   ↓
develop
   ↓
main
```

Ainsi, une fonctionnalité n'atteint `develop` qu'après validation.

La branche `main` est réservée aux versions considérées comme stables.

---

## B0.4 Configuration de `.gitignore`

Un fichier `.gitignore` a été créé afin d'éviter de versionner des fichiers
locaux, temporaires ou sensibles.

Le contenu retenu est :

```gitignore
# ============================================================
# METEOGPT BACKEND
# ============================================================


# ------------------------------------------------------------
# PYTHON
# ------------------------------------------------------------

__pycache__/
*.py[cod]
*.pyo
*.pyd


# ------------------------------------------------------------
# ENVIRONNEMENTS VIRTUELS
# ------------------------------------------------------------

.venv/
venv/
env/


# ------------------------------------------------------------
# VARIABLES D'ENVIRONNEMENT / SECRETS
# ------------------------------------------------------------

.env
.env.local
.env.development
.env.production

!.env.example


# ------------------------------------------------------------
# IDE
# ------------------------------------------------------------

.vscode/
.idea/

*.swp
*.swo


# ------------------------------------------------------------
# TESTS / COVERAGE
# ------------------------------------------------------------

.pytest_cache/
.coverage
htmlcov/


# ------------------------------------------------------------
# LOGS
# ------------------------------------------------------------

logs/
*.log


# ------------------------------------------------------------
# QDRANT LOCAL
# ------------------------------------------------------------

data/qdrant/
qdrant_storage/


# ------------------------------------------------------------
# DONNÉES GÉNÉRÉES PAR LE PIPELINE
# ------------------------------------------------------------

data/chunks*.json
data/embeddings*.json

data/registry/
data/raw/
data/processed/


# ------------------------------------------------------------
# UPLOADS / TEMP
# ------------------------------------------------------------

uploads/
tmp/
temp/


# ------------------------------------------------------------
# AUDIO
# ------------------------------------------------------------

*.wav
*.mp3
*.ogg
*.m4a


# ------------------------------------------------------------
# CACHE MODÈLES
# ------------------------------------------------------------

.cache/
huggingface/


# ------------------------------------------------------------
# NOTEBOOKS
# ------------------------------------------------------------

.ipynb_checkpoints/


# ------------------------------------------------------------
# SYSTÈME
# ------------------------------------------------------------

.DS_Store
Thumbs.db
desktop.ini


# ------------------------------------------------------------
# TEMPORAIRES
# ------------------------------------------------------------

*.tmp
*.temp
*.bak
```

Cette configuration est particulièrement importante pour plusieurs raisons.

Le dossier :

```text
.venv/
```

contient l'environnement Python local et ne doit pas être envoyé sur GitHub.

Le fichier :

```text
.env
```

contient les futures clés et tokens de l'application et doit rester uniquement
sur la machine de développement.

Les répertoires de stockage Qdrant, les embeddings et les chunks sont également
exclus car ils sont générés automatiquement.

---

## B0.5 Utilisation de `.env.example`

Le fichier :

```text
.env
```

est privé et ignoré par Git.

En revanche, le fichier :

```text
.env.example
```

est versionné.

Son rôle est de documenter les variables nécessaires au fonctionnement de
l'application sans exposer leur valeur réelle.

Le principe est donc :

```text
.env
│
├── vraies clés
├── vrais tokens
└── valeurs locales

        ↓

jamais envoyé sur GitHub
```

alors que :

```text
.env.example
│
├── noms des variables
├── structure attendue
└── valeurs non sensibles

        ↓

versionné dans Git
```

---

## B0.6 Configuration de `.gitattributes`

Un fichier `.gitattributes` a également été ajouté.

Il contient :

```gitattributes
* text=auto
```

Cette configuration permet à Git de gérer automatiquement les différences de
fin de ligne entre Windows et d'autres environnements.

Durant le développement, Git peut afficher un message du type :

```text
LF will be replaced by CRLF
```

Ce message n'indique pas une erreur.

Il signifie simplement que Git harmonise les fins de lignes en fonction du
système d'exploitation.

---

## B0.7 Tag initial du backend

Un tag initial a été créé :

```text
backend-v0.1
```

Il correspond à l'état du dépôt avant le développement des différentes phases
du backend.

Ce tag permet de conserver un point de référence stable.

---

## B0.8 Validation de la phase B0

La phase B0 est considérée comme validée lorsque :

- le dépôt GitHub existe ;
- le dépôt local communique avec GitHub ;
- les branches `main` et `develop` existent ;
- `.env` est ignoré ;
- `.venv` est ignoré ;
- `.env.example` est versionné ;
- les données générées ne sont pas versionnées ;
- le tag `backend-v0.1` existe.

La phase B0 fournit ainsi une base Git propre pour poursuivre le développement.

**Statut : VALIDÉ**

---

# B1 — Mise en place de l'environnement de développement

## B1.1 Objectif

La phase B1 consiste à préparer un environnement Python local dédié au backend
MeteoGPT.

L'objectif est de disposer d'un environnement :

- isolé ;
- reproductible ;
- indépendant de Google Colab ;
- adapté au développement local ;
- compatible avec les futures bibliothèques IA ;
- facilement reconstruisible à partir du dépôt Git.

---

## B1.2 Choix de la version Python

La machine disposait initialement de Python 3.13.

Cependant, Python 3.11 a été retenu pour le backend MeteoGPT.

Ce choix est lié à la compatibilité attendue avec l'écosystème utilisé dans le
projet :

- FastAPI ;
- Qdrant ;
- SentenceTransformers ;
- PyTorch ;
- LangGraph ;
- bibliothèques Google ;
- composants du pipeline RAG.

La version installée est :

```text
Python 3.11.9
```

Python 3.13 reste installé sur la machine, mais l'environnement MeteoGPT utilise
exclusivement Python 3.11.

---

## B1.3 Création de l'environnement virtuel

Un environnement virtuel a été créé à la racine du projet.

Commande utilisée :

```powershell
py -3.11 -m venv .venv
```

Cette commande crée le dossier :

```text
.venv/
```

qui contient notamment :

```text
.venv/
├── Scripts/
├── Lib/
└── pyvenv.cfg
```

L'environnement virtuel permet d'isoler les dépendances du projet de celles
installées globalement sur Windows.

---

## B1.4 Activation sous PowerShell

PowerShell empêchait initialement l'exécution du script d'activation.

L'erreur provenait de la politique d'exécution des scripts Windows.

La configuration a été modifiée uniquement pour la session PowerShell actuelle
avec :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Puis l'environnement a été activé avec :

```powershell
.\.venv\Scripts\Activate.ps1
```

Après activation, le terminal affiche :

```text
(.venv)
```

devant l'invite PowerShell.

Exemple :

```text
(.venv) PS C:\...\MeteoGPT_Backend>
```

Cela indique que toutes les commandes Python exécutées dans ce terminal utilisent
désormais l'environnement virtuel.

---

## B1.5 Vérification de l'environnement Python

La version Python a été vérifiée avec :

```powershell
python --version
```

Résultat :

```text
Python 3.11.9
```

L'exécutable Python utilisé a ensuite été vérifié avec :

```powershell
python -c "import sys; print(sys.executable)"
```

Le chemin retourné correspond à :

```text
MeteoGPT_Backend\.venv\Scripts\python.exe
```

La commande :

```powershell
where.exe python
```

a également confirmé que le premier Python trouvé par Windows est celui de
l'environnement virtuel :

```text
MeteoGPT_Backend\.venv\Scripts\python.exe
```

Les autres versions de Python restent disponibles sur la machine mais ne sont pas
utilisées par le projet tant que `.venv` est actif.

---

## B1.6 Vérification de pip

La commande :

```powershell
python -m pip --version
```

a confirmé que `pip` appartient également à l'environnement virtuel.

Une mise à jour de pip a été effectuée.

La version utilisée après mise à jour est :

```text
pip 26.2.1
```

---

## B1.7 Gestion des dépendances

Deux fichiers ont été créés :

```text
requirements.txt
requirements-dev.txt
```

Cette séparation permet de distinguer :

```text
dépendances nécessaires au fonctionnement de l'application
```

et :

```text
dépendances uniquement nécessaires au développement et aux tests
```

---

## B1.8 Contenu de `requirements.txt`

Le fichier contient :

```text
fastapi
uvicorn[standard]
pydantic
pydantic-settings
python-dotenv
python-multipart
httpx
```

Ces dépendances correspondent à la première couche du backend.

À ce stade, les bibliothèques spécifiques au RAG ne sont pas encore ajoutées.

Elles seront intégrées uniquement lorsque le cœur IA sera connecté au backend.

Cette démarche évite de recopier inutilement tout l'environnement du notebook.

---

## B1.9 Contenu de `requirements-dev.txt`

Le fichier contient :

```text
-r requirements.txt

pytest
pytest-cov
```

La directive :

```text
-r requirements.txt
```

indique que toutes les dépendances runtime doivent également être installées
dans l'environnement de développement.

Les bibliothèques supplémentaires sont :

```text
pytest
pytest-cov
```

Elles seront utilisées pour les tests automatisés.

---

## B1.10 Installation des dépendances

L'installation est réalisée avec :

```powershell
python -m pip install -r requirements-dev.txt
```

Les principales bibliothèques installées sont notamment :

```text
fastapi           0.141.1
uvicorn           0.53.0
pydantic          2.13.5
pydantic-settings 2.15.0
httpx             0.28.1
pytest            9.1.1
pytest-cov        7.1.0
python-dotenv     1.2.3
python-multipart  0.0.32
```

---

## B1.11 Vérification des dépendances

La commande :

```powershell
python -m pip list
```

permet de vérifier les bibliothèques installées.

Une seconde vérification a été réalisée en important directement les principaux
modules :

```powershell
python -c "import fastapi, uvicorn, pydantic, pydantic_settings, dotenv, multipart, httpx, pytest; print('TOUTES LES DEPENDANCES BACKEND SONT OK')"
```

Résultat :

```text
TOUTES LES DEPENDANCES BACKEND SONT OK
```

Cette vérification confirme que :

- les packages sont réellement installés ;
- Python les trouve correctement ;
- les imports sont fonctionnels ;
- l'environnement virtuel est opérationnel.

---

## B1.12 Problème rencontré lors de l'installation

Lors d'une première tentative, la commande :

```powershell
python -m pip install -r requirements-dev.txt
```

n'avait installé aucune dépendance.

L'analyse a montré que les fichiers :

```text
requirements.txt
requirements-dev.txt
```

avaient été créés mais étaient vides.

Le problème ne provenait donc ni de Python ni de l'environnement virtuel.

Après remplissage des deux fichiers, l'installation a été relancée et s'est
terminée correctement.

Cette vérification a permis d'éviter d'interpréter à tort le problème comme une
erreur de configuration de Python.

---

## B1.13 Hygiène Git de l'environnement

Après la création de `.venv`, Git affichait initialement :

```text
?? .venv/
```

Cela indiquait que le dossier n'était pas correctement ignoré.

Une branche corrective a donc été créée :

```text
fix/b1-git-hygiene
```

Cette branche a permis de corriger :

- `.gitignore` ;
- `.env.example` ;
- l'ancien fichier `.env.exemple` ;
- certains fichiers de documentation ;
- les fichiers requirements.

L'ancien fichier :

```text
.env.exemple
```

a été supprimé.

Le nom correct retenu est :

```text
.env.example
```

---

## B1.14 Validation Git de `.venv`

La commande :

```powershell
git check-ignore -v .venv/
```

permet de vérifier que `.venv` est correctement ignoré.

Après correction, `.venv` n'apparaît plus dans :

```powershell
git status --short
```

L'environnement virtuel reste donc uniquement sur la machine locale.

---

## B1.15 Commits Git de la phase B1

La phase B1 a été développée dans :

```text
feature/b1-environment
```

Le commit principal est :

```text
chore: configure local backend development environment
```

Une correction complémentaire a été réalisée dans :

```text
fix/b1-git-hygiene
```

avec le commit :

```text
fix: clean B1 Git configuration and environment files
```

Les deux branches ont ensuite été fusionnées dans :

```text
develop
```

avec les merges :

```text
merge: complete B1 backend environment
```

et :

```text
merge: fix B1 Git hygiene
```

---

## B1.16 Validation de la phase B1

La phase B1 est considérée comme validée car :

- Python 3.11.9 est installé ;
- l'environnement `.venv` fonctionne ;
- Python provient bien de `.venv` ;
- pip fonctionne dans `.venv` ;
- les dépendances backend sont installées ;
- les imports sont fonctionnels ;
- les fichiers requirements permettent de reconstruire l'environnement ;
- `.venv` est ignoré par Git ;
- les corrections Git ont été fusionnées dans `develop`.

L'environnement de développement backend est donc prêt.

**Statut : VALIDÉ**

---

# B2 — Mise en place de la configuration applicative

## B2.1 Objectif

La phase B2 vise à centraliser toute la configuration de MeteoGPT.

L'objectif principal est d'éviter de disperser les paramètres directement dans
les différents fichiers Python.

Dans le notebook expérimental, certains chemins étaient spécifiques à Google
Colab, par exemple :

```text
/content/drive/MyDrive/MeteoGPT
```

Ces chemins ne doivent pas apparaître dans le backend.

De la même manière, les éléments suivants ne doivent jamais être écrits
directement dans le code :

- clé Gemini ;
- token WhatsApp ;
- identifiant du numéro WhatsApp ;
- token de vérification Meta ;
- chemin Qdrant ;
- URL ANACIM répétée dans plusieurs modules.

Le principe retenu est :

```text
.env
  ↓
Pydantic Settings
  ↓
config.py
  ↓
application
```

---

## B2.2 Branche de développement

La phase B2 est développée dans :

```text
feature/b2-configuration
```

Cette branche est créée à partir de `develop` après validation de B1.

Elle contient uniquement les modifications liées à la configuration.

---

## B2.3 Création de l'arborescence backend

Les répertoires suivants ont été créés :

```text
backend/
backend/app/
backend/app/core/
backend/tests/
```

Les fichiers `__init__.py` ont également été créés afin que ces répertoires
soient reconnus comme packages Python.

L'arborescence obtenue est :

```text
MeteoGPT_Backend/
│
├── backend/
│   ├── __init__.py
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   │
│   │   └── core/
│   │       ├── __init__.py
│   │       └── config.py
│   │
│   └── tests/
│       ├── __init__.py
│       └── test_config.py
│
├── .env
├── .env.example
├── requirements.txt
└── requirements-dev.txt
```

---

## B2.4 Création du fichier `.env`

Un fichier :

```text
.env
```

a été créé à la racine du projet.

Ce fichier contient la configuration locale de l'application.

Il est explicitement ignoré par Git.

La commande :

```powershell
git check-ignore -v .env
```

a confirmé que la règle du `.gitignore` est correctement appliquée.

Le fichier `.env` n'apparaît donc pas dans :

```powershell
git status
```

---

## B2.5 Variables de configuration

La configuration locale est organisée en plusieurs groupes.

### Application

```env
APP_NAME=MeteoGPT Backend
APP_ENV=development
DEBUG=true

API_V1_PREFIX=/api/v1
```

Le backend fonctionne actuellement dans l'environnement :

```text
development
```

Il ne s'agit donc pas encore d'un environnement de production.

---

## B2.6 Configuration des chemins

Les chemins relatifs utilisés sont :

```env
DATA_DIR=data
LOG_DIR=logs
```

Ces chemins sont volontairement relatifs.

Ils seront transformés automatiquement en chemins absolus à partir de la racine
du projet.

Cette stratégie évite d'écrire un chemin dépendant de l'ordinateur du
développeur.

---

## B2.7 Configuration Qdrant

Les paramètres retenus sont :

```env
QDRANT_COLLECTION=meteogpt_api_chunks
QDRANT_PATH=data/qdrant
```

La collection utilisée reste donc :

```text
meteogpt_api_chunks
```

qui correspond à celle utilisée durant la phase expérimentale.

Qdrant sera utilisé en mode local pendant la phase de développement.

Aucun Qdrant Cloud payant n'est utilisé.

---

## B2.8 Configuration ANACIM

L'URL de l'API ANACIM est centralisée :

```env
ANACIM_API_URL=http://213.154.77.59:8000/mat/api_meteo.php
```

Cette valeur sera ensuite utilisée par le service d'actualisation.

Le backend n'aura donc pas besoin de redéfinir cette URL dans plusieurs modules.

---

## B2.9 Configuration Gemini

La configuration prévoit :

```env
GEMINI_API_KEY=
```

La valeur réelle sera définie uniquement dans le fichier `.env`.

Aucune clé Gemini ne doit être enregistrée dans GitHub.

Le fichier `.env.example` conserve uniquement :

```env
GEMINI_API_KEY=
```

afin d'indiquer qu'une clé sera nécessaire.

---

## B2.10 Configuration WhatsApp Cloud API

L'intégration future avec WhatsApp utilise directement l'API officielle de Meta.

Twilio n'est pas utilisé.

Les variables prévues sont :

```env
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_API_VERSION=v23.0
```

Ces valeurs seront renseignées lors de la phase d'intégration WhatsApp.

À ce stade, les champs sensibles restent vides.

---

## B2.11 Feature flags

Plusieurs fonctionnalités peuvent être activées ou désactivées depuis la
configuration.

Les paramètres sont :

```env
ENABLE_SPEECH=true
ENABLE_ADMIN_UPDATE=true
ENABLE_WHATSAPP=false
```

Le fonctionnement initial est donc :

```text
Speech               → activé
Update administratif → activé
WhatsApp              → désactivé
```

WhatsApp sera activé uniquement lorsque l'intégration correspondante sera
terminée.

---

## B2.12 Logging

Le niveau de log est configurable :

```env
LOG_LEVEL=INFO
```

Les valeurs autorisées sont :

```text
DEBUG
INFO
WARNING
ERROR
CRITICAL
```

---

## B2.13 Création de `config.py`

Le fichier :

```text
backend/app/core/config.py
```

centralise la configuration de l'application.

La racine du projet est calculée automatiquement :

```python
PROJECT_ROOT = Path(__file__).resolve().parents[3]
```

Cette instruction permet d'identifier dynamiquement :

```text
MeteoGPT_Backend/
```

sans écrire le chemin absolu de la machine.

---

## B2.14 Classe `Settings`

La configuration est définie avec `pydantic-settings`.

Une classe :

```python
Settings
```

regroupe les différentes catégories de paramètres :

```text
Application
Paths
Qdrant
ANACIM
Gemini
WhatsApp
Features
Logging
```

Les valeurs peuvent être récupérées automatiquement depuis :

```text
variables d'environnement
+
.env
```

---

## B2.15 Résolution automatique des chemins

Trois propriétés permettent d'obtenir les chemins absolus :

```python
absolute_data_dir
absolute_log_dir
absolute_qdrant_path
```

Par exemple :

```python
settings.absolute_qdrant_path
```

retourne :

```text
C:\Users\...\MeteoGPT_Backend\data\qdrant
```

alors que la configuration ne contient que :

```text
data/qdrant
```

Cette approche rend le projet portable.

Il pourra être exécuté sur une autre machine sans modifier le code.

---

## B2.16 Singleton de configuration

La fonction :

```python
get_settings()
```

est décorée avec :

```python
@lru_cache
```

Cela signifie que la configuration n'est pas recréée à chaque utilisation.

Une instance peut être réutilisée par les différents services du backend.

---

## B2.17 Premier test manuel de configuration

La configuration a été testée avec :

```powershell
python -c "from backend.app.core.config import get_settings; s=get_settings(); print(s)"
```

Le résultat confirme notamment :

```text
app_name='MeteoGPT Backend'
app_env='development'
debug=True
api_v1_prefix='/api/v1'
qdrant_collection='meteogpt_api_chunks'
enable_speech=True
enable_admin_update=True
enable_whatsapp=False
log_level='INFO'
```

---

## B2.18 Vérification de la racine et de Qdrant

Une deuxième commande a été utilisée :

```powershell
python -c "from backend.app.core.config import get_settings; s=get_settings(); print('ENV=', s.app_env); print('ROOT=', s.absolute_data_dir.parent); print('QDRANT=', s.absolute_qdrant_path); print('WHATSAPP=', s.enable_whatsapp)"
```

Résultat :

```text
ENV= development
ROOT= C:\Users\diaai\Documents\PFE ANACIM\MeteoGPT\MeteoGPT_Backend
QDRANT= C:\Users\diaai\Documents\PFE ANACIM\MeteoGPT\MeteoGPT_Backend\data\qdrant
WHATSAPP= False
```

Ces résultats confirment que :

- l'environnement est correctement chargé ;
- la racine du projet est correcte ;
- le chemin Qdrant est correctement construit ;
- WhatsApp est désactivé par défaut.

---

## B2.19 Tests automatisés de configuration

Un fichier de test a été créé :

```text
backend/tests/test_config.py
```

Les tests vérifient :

```text
1. environnement par défaut
2. préfixe API
3. existence de PROJECT_ROOT
4. chemin absolu du dossier data
5. chemin absolu Qdrant
6. désactivation de WhatsApp par défaut
```

Les tests sont exécutés avec :

```powershell
pytest backend/tests/test_config.py -v
```

Lors de la première tentative, aucun test n'a été détecté :

```text
collected 0 items
```

Après correction du contenu du fichier de test, une nouvelle exécution a été
réalisée.

Résultat :

```text
collected 6 items

test_default_environment PASSED
test_api_prefix PASSED
test_project_root_exists PASSED
test_absolute_data_dir PASSED
test_absolute_qdrant_path PASSED
test_whatsapp_disabled_by_default PASSED

6 passed
```

Les six tests passent donc correctement.

---

## B2.20 Vérification finale de la configuration

Un contrôle final a été effectué.

Branche :

```text
feature/b2-configuration
```

Environnement :

```text
development
```

Racine :

```text
C:\Users\diaai\Documents\PFE ANACIM\MeteoGPT\MeteoGPT_Backend
```

Qdrant :

```text
C:\Users\diaai\Documents\PFE ANACIM\MeteoGPT\MeteoGPT_Backend\data\qdrant
```

WhatsApp :

```text
False
```

Tests :

```text
6 passed
```

Le statut Git avant commit contenait uniquement :

```text
M .env.example
?? backend/
```

Le fichier `.env` n'apparaissait pas, ce qui confirme qu'il est correctement
ignoré.

---

## B2.21 Résultat de la phase B2

À la fin de cette phase, la configuration de MeteoGPT est centralisée selon
l'architecture :

```text
                .env
                  │
                  ▼
         Pydantic Settings
                  │
                  ▼
             config.py
                  │
        ┌─────────┼─────────┐
        ▼         ▼         ▼
     FastAPI    Services    RAG
```

Cette organisation permet aux futurs composants de récupérer leur configuration
depuis un point unique.

Elle évite :

```text
chemins codés en dur
clés API dans le code
tokens dans Git
configuration dupliquée
dépendance à Google Colab
```

---

## B2.22 Validation de la phase B2

La phase est considérée comme validée car :

- `PROJECT_ROOT` est correctement calculé ;
- `.env` est ignoré par Git ;
- `.env.example` est versionnable ;
- Pydantic Settings charge correctement la configuration ;
- les chemins relatifs deviennent des chemins absolus ;
- la configuration Qdrant est définie ;
- l'URL ANACIM est centralisée ;
- Gemini est prévu dans la configuration ;
- WhatsApp Cloud API est prévu dans la configuration ;
- les feature flags fonctionnent ;
- six tests automatisés passent ;
- aucune dépendance à Google Colab n'est nécessaire.

**Statut : VALIDÉ**

---

# État du backend après B2

À l'issue des trois premières phases, la structure fonctionnelle du projet est :

```text
MeteoGPT_Backend/
│
├── .git/
├── .venv/                     # local uniquement
│
├── backend/
│   ├── __init__.py
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   │
│   │   └── core/
│   │       ├── __init__.py
│   │       └── config.py
│   │
│   └── tests/
│       ├── __init__.py
│       └── test_config.py
│
├── src/
│   └── __init__.py
│
├── .env                       # local / ignoré
├── .env.example               # versionné
├── .gitignore
├── .gitattributes
│
├── requirements.txt
├── requirements-dev.txt
├── README.md
│
└── docs/
    └── backend_development.md
```

Les fondations nécessaires au développement du backend sont donc en place.

La prochaine étape pourra consister à créer l'application FastAPI minimale et à
valider son fonctionnement indépendamment du pipeline RAG.



# B3 — Initialisation de l'API FastAPI

## B3.1 Objectif

La phase B3 consiste à mettre en place la première couche HTTP du backend
MeteoGPT à l'aide de FastAPI.

L'objectif n'est pas encore d'intégrer le pipeline RAG, Qdrant, Gemini ou
WhatsApp.

Cette phase sert uniquement à vérifier que :

- l'application FastAPI démarre correctement ;
- une route de santé est accessible ;
- la documentation Swagger est générée ;
- le schéma OpenAPI est disponible ;
- la couche API peut être testée automatiquement.

Cette séparation est importante car elle permet de valider l'infrastructure
HTTP indépendamment du cœur intelligent de MeteoGPT.

---

## B3.2 Structure ajoutée

La structure suivante a été introduite :

```text
backend/
├── app/
│   ├── main.py
│   │
│   ├── core/
│   │   └── config.py
│   │
│   └── api/
│       └── routes/
│           └── health.py
│
└── tests/
    ├── test_config.py
    └── test_health.py
```

Le fichier `main.py` constitue désormais le point d'entrée de l'application
FastAPI.

Le dossier `api/routes` est destiné à contenir progressivement les différentes
routes exposées par le backend.

---

## B3.3 Création de l'application FastAPI

L'application est créée à travers une fonction dédiée :

```python
create_app()
```

Cette approche permet de centraliser l'initialisation de FastAPI.

Elle facilitera par la suite :

- l'ajout de nouveaux routers ;
- les tests ;
- la gestion de plusieurs environnements ;
- l'évolution de la configuration ;
- l'ajout de middlewares.

L'instance principale reste disponible sous la forme :

```python
app = create_app()
```

Cette instance est utilisée par Uvicorn pour démarrer le serveur.

---

## B3.4 Endpoint de santé

Un premier endpoint a été créé :

```text
GET /health
```

Son rôle est uniquement de vérifier que le backend répond correctement.

Il retourne notamment :

```json
{
  "status": "ok",
  "service": "MeteoGPT Backend",
  "environment": "development"
}
```

Cet endpoint reste volontairement léger.

À ce stade, il ne vérifie pas :

- Qdrant ;
- Gemini ;
- le Retriever ;
- LangGraph ;
- l'API ANACIM ;
- WhatsApp.

Cette décision permet de conserver un test de disponibilité rapide du backend.

---

## B3.5 Documentation automatique

FastAPI génère automatiquement plusieurs interfaces utiles.

La documentation Swagger est disponible à l'adresse :

```text
/docs
```

Le schéma OpenAPI est disponible à :

```text
/openapi.json
```

Une documentation ReDoc est également disponible à :

```text
/redoc
```

Swagger permet de visualiser les routes disponibles et facilitera les futurs
tests des endpoints sans avoir besoin de créer immédiatement une interface
graphique.

---

## B3.6 Serveur local Uvicorn

Le backend est exécuté localement avec Uvicorn.

En l'absence de configuration explicite du host et du port, Uvicorn utilise les
valeurs par défaut :

```text
host = 127.0.0.1
port = 8000
```

L'adresse locale du serveur devient donc :

```text
http://127.0.0.1:8000
```

L'adresse `127.0.0.1` correspond à la machine locale.

Le port `8000` est le port par défaut utilisé par Uvicorn.

Les routes sont ensuite ajoutées à cette adresse de base.

Exemple :

```text
http://127.0.0.1:8000/health
```

---

## B3.7 Comportement de la route racine

Aucune route :

```text
/
```

n'a volontairement été créée.

Par conséquent, l'accès direct à :

```text
http://127.0.0.1:8000/
```

retourne :

```json
{
  "detail": "Not Found"
}
```

avec un code HTTP `404`.

Ce comportement est normal.

Il ne signifie pas que le serveur est en erreur.

Il indique simplement qu'aucun endpoint n'est associé à la route racine.

Les routes actuellement utiles sont :

```text
/health
/docs
/openapi.json
/redoc
```

---

## B3.8 Tests automatisés

Trois nouveaux tests ont été ajoutés pour vérifier :

1. le fonctionnement de `/health` ;
2. la disponibilité du schéma OpenAPI ;
3. la disponibilité de Swagger.

Les tests précédents de configuration ont également été réexécutés afin de
vérifier qu'aucune régression n'a été introduite.

Le résultat global obtenu est :

```text
9 passed
```

Les neuf tests correspondent à :

```text
6 tests de configuration
+
3 tests FastAPI
```

Tous les tests passent avec succès.

---

## B3.9 Warnings observés

Deux warnings provenant des dépendances FastAPI, Starlette, HTTPX et AnyIO ont
été observés durant les tests.

Ils concernent des dépréciations internes dans les bibliothèques utilisées par
`TestClient`.

Ces warnings ne correspondent pas à une erreur du code MeteoGPT.

Comme les tests passent correctement, aucune modification de version n'a été
effectuée uniquement pour supprimer ces avertissements.

---

## B3.10 Validation manuelle

La validation manuelle a confirmé que :

```text
http://127.0.0.1:8000/health
```

retourne correctement l'état du backend.

La documentation :

```text
http://127.0.0.1:8000/docs
```

s'ouvre correctement et affiche la route :

```text
GET /health
```

Le serveur Uvicorn démarre sans erreur et l'application FastAPI est
opérationnelle.

---

## B3.11 Résultat de la phase

À la fin de B3, la première couche applicative du backend est opérationnelle.

L'architecture actuelle peut être représentée ainsi :

```text
Client HTTP
    ↓
Uvicorn
    ↓
FastAPI
    ↓
Router
    ↓
GET /health
```

Le backend peut désormais recevoir des requêtes HTTP.

Aucun composant IA n'est encore chargé dans cette couche.

Cette séparation permet de poursuivre l'intégration progressivement sans
mélanger les problèmes liés au serveur HTTP avec ceux liés au pipeline RAG.

---

## B3.12 Validation de la phase B3

La phase B3 est considérée comme validée car :

- FastAPI démarre correctement ;
- Uvicorn fonctionne ;
- `/health` est opérationnel ;
- Swagger est accessible ;
- OpenAPI est généré ;
- les tests automatisés passent ;
- les tests précédents restent valides ;
- aucun composant IA n'est chargé inutilement au démarrage ;
- la phase a été versionnée puis fusionnée dans `develop`.

**Statut : VALIDÉ**



## B4 — Intégration Chat / RAG

### Objectif

La phase B4 a pour objectif d'intégrer le pipeline RAG validé de MeteoGPT au backend FastAPI, tout en conservant une séparation claire entre la couche applicative et les modules IA.

### Modules RAG intégrés

Les modules suivants sont utilisés par le backend :

- `agent.py`
- `retriever.py`
- `generation.py`
- `speech.py`
- `rag_pipeline.py`

Le pipeline public principal repose sur :

- `process_text_request`
- `process_audio_request`
- `process_request`

### Architecture RAG intégrée

Le pipeline MeteoGPT repose sur :

- un Agent LangGraph ;
- un Retriever hybride ;
- des embeddings `intfloat/multilingual-e5-base` ;
- BM25 ;
- Reciprocal Rank Fusion ;
- filtres temporels, géographiques et métier ;
- une base vectorielle Qdrant locale ;
- Gemini pour la génération ;
- un mode multimodal pour l'exploitation d'images météorologiques.

### Migration des chemins Colab vers le backend

Les dépendances aux chemins Google Colab et Google Drive ont été supprimées du runtime.

Les données persistent désormais avec des chemins relatifs au projet, par exemple :

```text
data/extracted/api/page_images/...
data/extracted/api/visuals/...
data/qdrant