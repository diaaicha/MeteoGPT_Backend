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
```

# B5 — Logs, erreurs et observabilité

### Objectif

La phase B5 introduit une observabilité légère dans le backend MeteoGPT afin de faciliter le diagnostic des requêtes, des erreurs et des performances du pipeline RAG, sans ajouter de solution de monitoring externe lourde.

### Logging centralisé

Le backend utilise désormais le module standard `logging` de Python.

La configuration est centralisée dans :

```text
backend/app/core/logging.py
```

Les logs sont envoyés :

- dans la console ;
- dans le fichier `logs/meteogpt_backend.log`.

Le fichier de log utilise une rotation afin d’éviter une croissance non contrôlée.

### Identifiants de traçabilité

Deux identifiants sont utilisés :

- `request_id` : identifie une requête HTTP individuelle ;
- `thread_id` : identifie une conversation MeteoGPT.

Chaque requête HTTP reçoit automatiquement un UUID exposé dans l’en-tête :

```text
X-Request-ID
```

Le `request_id` permet de relier les logs HTTP aux logs générés pendant le traitement Chat.

Le `thread_id` permet quant à lui de suivre une même conversation sur plusieurs requêtes.

### Logs HTTP

Le middleware :

```text
backend/app/middleware/request_logging.py
```

journalise les informations suivantes :

- méthode HTTP ;
- chemin appelé ;
- statut HTTP ;
- latence de la requête ;
- `request_id`.

Les niveaux de logs utilisés sont :

```text
2xx / 3xx -> INFO
4xx       -> WARNING
5xx       -> ERROR
```

### Logs Chat et RAG

Le service Chat journalise les principales métadonnées techniques du traitement :

- `request_id` ;
- `thread_id` ;
- route choisie ;
- intent identifié ;
- mode de génération ;
- exécution ou non du retrieval ;
- utilisation ou non du multimodal ;
- statut `grounded` ;
- latence de l’Agent ;
- latence du Retrieval ;
- latence de la Generation ;
- latence totale ;
- type d’erreur éventuel.

Les latences déjà calculées par le pipeline RAG sont réutilisées afin d’éviter de dupliquer les mesures.

### Protection des données

Les logs MeteoGPT ne doivent pas contenir :

- `GEMINI_API_KEY` ;
- `WHATSAPP_ACCESS_TOKEN` ;
- `WHATSAPP_VERIFY_TOKEN` ;
- secrets contenus dans `.env` ;
- contenu audio binaire ;
- prompt complet envoyé au LLM ;
- question utilisateur complète ;
- réponse Gemini complète ;
- contenu intégral des chunks récupérés.

Les anciens `print()` temporaires utilisés pour le diagnostic de Gemini dans `generation.py` ont été supprimés.

### Gestion des erreurs

Les erreurs continuent d’être gérées au niveau des différents composants existants du backend.

L’observabilité ajoutée en B5 permet désormais de distinguer plus facilement :

- les erreurs HTTP ;
- les erreurs du service Chat ;
- les erreurs retournées par le pipeline RAG ;
- les erreurs ou timeouts provenant de la génération.

Une requête ayant échoué conserve également son `request_id`, ce qui permet de retrouver les événements correspondants dans les logs.

### Tests d’observabilité

Un fichier de tests spécifique a été ajouté :

```text
backend/tests/test_observability.py
```

Les tests vérifient notamment :

- la présence de `X-Request-ID` ;
- la validité UUID du `request_id` ;
- l’unicité du `request_id` entre deux requêtes ;
- la présence du `request_id` lors d’une erreur HTTP `422` ;
- la présence du `request_id` lors d’une erreur HTTP `500`.

### Validation

À la fin de la phase B5, l’ensemble des tests backend est validé :

```text
22 passed
```

Le warning Starlette / AnyIO observé pendant les tests provient d’une dépendance externe et reste non bloquant.

### Architecture d’observabilité obtenue

```text
Utilisateur
    ↓
FastAPI
    ↓
Middleware HTTP
    ├── request_id
    ├── statut HTTP
    └── latence HTTP
    ↓
Chat service
    ├── request_id
    ├── thread_id
    ├── route
    ├── intent
    ├── mode de génération
    └── latences RAG
    ↓
Agent
    ↓
Retriever / Qdrant
    ↓
Generation / Gemini
    ↓
Réponse MeteoGPT
```

Cette solution reste volontairement légère, locale et proportionnée aux besoins du PFE MeteoGPT.


---

# 27. B6 - Actualisation ANACIM

## Objectif

B6 permet au backend MeteoGPT d'actualiser le corpus météorologique à partir de l'API ANACIM sans reconstruire entièrement Qdrant.

Pipeline :

```text
API ANACIM
-> détection new / modified / resume_processing
-> téléchargement ou reprise du PDF local
-> extraction
-> chunks
-> embeddings
-> mise à jour JSON
-> mise à jour incrémentale Qdrant
-> actualisation du registre
-> refresh BM25
```

## Endpoint d'administration

```text
POST /api/v1/admin/update
```

Par défaut :

```json
{
  "dry_run": true
}
```

Le dry-run interroge l'API ANACIM et détecte les bulletins à traiter sans modifier le corpus.

## Activer ou désactiver l'actualisation

Variable de configuration :

```text
ENABLE_ADMIN_UPDATE=true
```

- `true` : le service d'actualisation est autorisé ;
- `false` : le service retourne `admin_update_disabled`.

> `ENABLE_ADMIN_UPDATE` est un interrupteur de fonctionnalité. Il ne constitue pas une authentification administrateur.

## Lancer un dry-run

```powershell
python -c "import json; from backend.app.services.update_service import run_anacim_update; print(json.dumps(run_anacim_update(dry_run=True), ensure_ascii=False, indent=2, default=str))"
```

## Lancer une actualisation réelle

```powershell
python -c "import json; from backend.app.services.update_service import run_anacim_update; print(json.dumps(run_anacim_update(dry_run=False), ensure_ascii=False, indent=2, default=str))"
```

## Mise à jour incrémentale de Qdrant

L'actualisation Qdrant est incrémentale.

Pour un nouveau document :

```text
nouveaux chunks
-> nouveaux embeddings
-> upsert Qdrant
```

La collection existante n'est pas supprimée.

Pour un document modifié :

```text
source_file du document modifié
-> suppression ciblée des anciens points
-> upsert des nouveaux points
```

Les autres documents présents dans la collection restent inchangés.

Le pipeline peut réutiliser le client Qdrant déjà ouvert par le Retriever afin d'éviter l'ouverture simultanée de plusieurs clients sur le même stockage local.

## Reprise après interruption

Si un bulletin a été téléchargé mais que le pipeline échoue avant la fin du traitement, son état permet une reprise avec :

```text
resume_processing
```

Si le PDF local existe, est un fichier valide et possède une taille supérieure à zéro, il est réutilisé sans nouveau téléchargement réseau.

Les indicateurs suivants permettent de distinguer les cas :

```text
pdf_ready
pdf_downloaded
pdf_reused
```

Exemple de reprise :

```text
pdf_ready      = 4
pdf_downloaded = 0
pdf_reused     = 4
```

## Synchronisation avec le Retriever

Après une actualisation réussie :

```text
Qdrant mis à jour
-> refresh_bm25_index()
-> Retriever hybride synchronisé
```

BM25 n'est pas reconstruit :

- pendant un `dry_run` ;
- lorsque le pipeline retourne `no_update` ;
- lorsque l'actualisation échoue.

## Dépendance PyMuPDF

Le pipeline utilise PyMuPDF pour l'extraction des PDF.

Dépendance runtime :

```text
pymupdf
```

Import utilisé dans le pipeline :

```python
import pymupdf as fitz
```

## Tests B6

Tests ciblés du pipeline d'actualisation :

```powershell
pytest .\backend\tests\test_update_pipeline.py -q
```

Tests du service :

```powershell
pytest .\backend\tests\test_update_service.py -q
```

Tests de l'endpoint admin :

```powershell
pytest .\backend\tests\test_admin_update.py -q
```

Tests complets du backend :

```powershell
pytest .\backend\tests -q
```

Résultat validé à la fin de B6 :

```text
31 passed
```

## Validation réelle de l'actualisation

### État avant actualisation

```text
PDF RAW              : 39
Documents distincts  : 39
Chunks JSON           : 345
Embeddings JSON       : 345
Points Qdrant         : 345
Dimension Qdrant      : 768
```

### Bulletins ajoutés le 21-09-2026

```text
Bulletin_Marine nationale_21-09-2026.pdf
Bulletin_Meteo soir_21-09-2026.pdf
Bulletin_Navigation cotiere_21-09-2026.pdf
Bulletin_Peche artisanale_21-09-2026.pdf
```

Nombre de nouveaux chunks :

```text
Marine nationale     : 4
Meteo soir           : 7
Navigation cotiere   : 6
Peche artisanale     : 3
Total                : 20
```

### État après actualisation

```text
Documents distincts  : 43
Chunks JSON           : 365
Embeddings JSON       : 365
Points Qdrant         : 365
BM25 chunks           : 365
BM25 localites        : 19
```

La collection Qdrant est passée de :

```text
345 -> 365 points
```

Les 345 anciens points ont été conservés et seuls les 20 nouveaux points ont été ajoutés.

## Validation du registre

Les quatre bulletins du 21-09-2026 ont été enregistrés avec :

```text
update_status = processed
processed_at  = renseigné
```

Après traitement :

```text
bulletins_a_traiter = 0
```

## Validation de l'idempotence

Une seconde exécution réelle du service d'actualisation a retourné :

```text
status = no_update
bulletins_a_traiter = 0
bm25_refresh = null
```

Le nombre de points Qdrant est resté :

```text
365
```

Cela confirme qu'une exécution répétée n'ajoute pas de doublons et ne reconstruit pas inutilement le corpus.

## Architecture B6 validée

```text
POST /api/v1/admin/update
        |
        v
update_service.py
        |
        v
meteogpt_update_api_pipeline.py
        |
        +--> API ANACIM
        |
        +--> registre API
        |
        +--> PDF locaux
        |
        +--> extraction
        |
        +--> chunks
        |
        +--> embeddings
        |
        +--> Qdrant incrémental
        |
        v
refresh_bm25_index()
        |
        v
Retriever synchronisé
```

## État final B6

```text
Pipeline update ANACIM          : validé
Dry-run                         : validé
Update réel                     : validé
Reprise après interruption      : validée
Qdrant incrémental              : validé
Remplacement ciblé              : validé
Client Qdrant partagé           : validé
Refresh BM25                    : validé
Endpoint admin                  : validé
Idempotence                     : validée
Tests backend                   : 31 passed
```


---

# 28. B7 — Intégration audio

## Objectif

La phase B7 a pour objectif d'intégrer au backend FastAPI les capacités de traitement audio déjà développées dans les composants du projet.

L'objectif principal est de permettre au backend de recevoir un fichier audio, d'en extraire la parole, de transmettre le texte obtenu au pipeline conversationnel existant puis de retourner une réponse structurée.

Cette phase ne crée pas un second pipeline conversationnel dédié à l'audio. Elle réutilise le même cœur applicatif que les requêtes textuelles.

Le principe retenu est :

```text
Audio utilisateur
      |
      v
Transcription
      |
      v
Texte
      |
      v
Pipeline conversationnel
      |
      v
Réponse
```

Cette séparation permet également de préparer l'intégration future des messages vocaux reçus depuis WhatsApp.

---

## Architecture retenue

La couche audio repose sur plusieurs niveaux :

```text
Client
  |
  v
FastAPI
  |
  v
Route audio
  |
  v
audio_service.py
  |
  v
speech.py
  |
  v
Pipeline conversationnel
  |
  v
Agent / Retriever / Generation
```

La couche HTTP reste séparée de la logique Speech et de la logique conversationnelle.

Cette organisation évite de placer directement le traitement audio dans les routes FastAPI.

---

## Endpoint audio

L'API expose une route dédiée au traitement audio :

```text
POST /api/v1/audio/chat
```

Cette route permet notamment de transmettre :

- un fichier audio ;
- un `thread_id` optionnel ;
- les paramètres nécessaires au traitement conversationnel.

Le fichier est transmis au service audio, qui centralise le traitement applicatif.

---

## Service audio

La logique principale de B7 est centralisée dans :

```text
backend/app/services/audio_service.py
```

Le service expose notamment la fonction :

```python
process_audio_chat(...)
```

Son rôle est d'orchestrer les différentes étapes nécessaires au traitement d'une requête vocale.

Le flux logique est :

```text
Fichier audio
      |
      v
Validation
      |
      v
Speech-to-Text
      |
      v
Transcription
      |
      v
Pipeline conversationnel
      |
      v
Réponse
```

Le service agit donc comme adaptateur entre la couche HTTP et les composants audio déjà présents dans le projet.

---

## Réutilisation de la couche Speech

Le backend réutilise le module :

```text
speech.py
```

qui contient les fonctions liées au traitement de la parole.

La phase B7 ne reconstruit donc pas les mécanismes Speech expérimentés précédemment.

Elle les intègre dans l'architecture applicative du backend.

Le principe retenu est :

```text
speech.py
    |
    v
fonctions Speech
    |
    v
audio_service.py
    |
    v
FastAPI
```

---

## Transcription audio

Lorsqu'un fichier audio est reçu, la première étape consiste à convertir la parole en texte.

La transcription obtenue devient ensuite l'entrée du pipeline conversationnel.

Le pipeline travaille donc toujours à partir d'une requête textuelle normalisée :

```text
Audio
  |
  v
Speech-to-Text
  |
  v
Texte utilisateur
  |
  v
Agent
```

Cette approche permet d'éviter de dupliquer la logique de routage et de compréhension déjà implémentée pour les messages texte.

---

## Réutilisation du pipeline conversationnel

Une fois la transcription obtenue, la requête rejoint le pipeline conversationnel existant.

Selon l'intention identifiée par l'Agent, le traitement peut emprunter différentes routes :

```text
Transcription
      |
      v
Agent
      |
      +--> réponse statique
      |
      +--> clarification
      |
      +--> direct LLM
      |
      +--> RAG
```

Lorsque le Retriever est nécessaire :

```text
Transcription
      |
      v
Agent
      |
      v
Retriever hybride
      |
      v
Qdrant
      |
      v
Generation
      |
      v
Réponse
```

Ainsi, les mécanismes RAG ne dépendent pas de l'origine textuelle ou audio de la requête.

---

## Gestion du thread conversationnel

Le traitement audio accepte également un :

```text
thread_id
```

Cet identifiant permet de conserver la continuité d'une conversation.

Lorsque le `thread_id` est fourni, il est transmis au pipeline conversationnel.

Cette logique est importante pour l'intégration WhatsApp prévue en B8, car le numéro WhatsApp de l'utilisateur pourra être utilisé comme identifiant stable de conversation.

Le principe est :

```text
Utilisateur
    |
    v
thread_id
    |
    v
Contexte conversationnel
```

---

## Mode de sortie

Le service audio permet de dissocier le traitement de l'entrée audio du format de sortie.

Le traitement peut notamment produire une réponse textuelle utilisée par les autres couches du backend.

Cette séparation est particulièrement utile pour WhatsApp :

```text
Message vocal WhatsApp
        |
        v
Audio
        |
        v
Transcription
        |
        v
Pipeline conversationnel
        |
        v
Réponse texte
        |
        v
WhatsApp
```

La génération éventuelle d'une réponse audio reste ainsi indépendante de la réception du fichier audio.

---

## Configuration

L'activation de la couche Speech reste contrôlée par le feature flag :

```text
ENABLE_SPEECH
```

Cette variable permet d'activer ou de désactiver la fonctionnalité sans modifier le code.

Le principe reste cohérent avec les autres fonctionnalités optionnelles du backend :

```text
.env
  |
  v
Settings
  |
  v
ENABLE_SPEECH
  |
  v
Couche audio
```

---

## Gestion des fichiers temporaires

Les fichiers audio reçus par le backend sont considérés comme des données temporaires.

Ils ne doivent pas être versionnés dans Git.

Les extensions audio sont déjà exclues par le `.gitignore`, notamment :

```text
*.wav
*.mp3
*.ogg
*.m4a
```

Cette règle permet d'éviter l'ajout accidentel de données audio utilisateur dans le dépôt.

---

## Validation fonctionnelle

La couche audio a été validée indépendamment de WhatsApp.

Les validations réalisées couvrent notamment :

```text
Route FastAPI audio        : validée
Réception fichier audio    : validée
Service audio              : validé
Transcription              : validée
Transmission thread_id     : validée
Pipeline conversationnel   : validé
Réponse structurée         : validée
Tests automatisés          : validés
```

Un test réel de transcription en français a également permis de confirmer le fonctionnement du traitement Speech.

---

## Rôle de B7 dans l'architecture globale

B7 introduit une couche réutilisable par plusieurs interfaces.

L'architecture devient :

```text
                 +----------------+
                 | Requête texte  |
                 +-------+--------+
                         |
                         v
                 Pipeline conversationnel
                         ^
                         |
                 +-------+--------+
                 | Service audio  |
                 +-------+--------+
                         ^
                         |
                 +-------+--------+
                 | Fichier audio  |
                 +----------------+
```

La couche audio est donc indépendante du canal de communication.

Cette décision permet à B8 de réutiliser B7 pour les messages vocaux WhatsApp sans recréer les mécanismes Speech.

---

## État final B7

```text
Endpoint audio              : validé
Service audio               : validé
Speech-to-Text              : validé
Réutilisation pipeline      : validée
Gestion thread_id           : validée
Séparation des couches      : validée
Tests automatisés           : validés
Test audio réel             : validé
```

La phase B7 fournit désormais au backend une couche audio exploitable par les futures interfaces.

**Statut : VALIDÉ**

---

# 29. B8 — Intégration WhatsApp Cloud API

## Objectif

La phase B8 vise à connecter le backend à WhatsApp à travers l'API officielle WhatsApp Cloud API de Meta.

L'objectif est de permettre à un utilisateur d'envoyer un message depuis WhatsApp, de transmettre ce message au pipeline conversationnel existant puis de recevoir directement la réponse dans la conversation WhatsApp.

WhatsApp constitue donc une nouvelle interface autour des services déjà développés.

Le principe général est :

```text
Utilisateur WhatsApp
        |
        v
WhatsApp Cloud API
        |
        v
Webhook Meta
        |
        v
FastAPI
        |
        v
Pipeline conversationnel
        |
        v
WhatsApp Cloud API
        |
        v
Utilisateur
```

La première partie de B8 concerne les messages texte.

La gestion des messages vocaux sera ajoutée dans la suite de la même phase.

---

## Branche de développement

La phase est développée dans :

```text
feature/b8-whatsapp
```

Les modifications restent isolées de `develop` jusqu'à validation complète de B8.

---

## Choix de WhatsApp Cloud API

L'intégration utilise directement :

```text
WhatsApp Cloud API
```

fournie par Meta.

Aucun intermédiaire tel que Twilio n'est utilisé dans cette intégration.

L'architecture retenue devient donc :

```text
Backend
   |
   v
Meta Graph API
   |
   v
WhatsApp
```

Cette approche permet au backend de communiquer directement avec l'infrastructure WhatsApp de Meta.

---

## Composants ajoutés

La phase B8 introduit principalement les fichiers suivants :

```text
backend/app/api/routes/whatsapp.py
backend/app/schemas/whatsapp.py
backend/app/services/whatsapp_service.py
backend/tests/test_whatsapp.py
```

Le router WhatsApp est également enregistré dans :

```text
backend/app/main.py
```

La configuration existante est réutilisée depuis :

```text
backend/app/core/config.py
```

---

## Architecture B8

L'organisation fonctionnelle est :

```text
Meta
 |
 v
whatsapp.py
(route FastAPI)
 |
 v
whatsapp_service.py
 |
 +--> extraction du message
 |
 +--> process_chat()
 |
 +--> envoi Graph API
 |
 v
Utilisateur WhatsApp
```

Les responsabilités sont ainsi séparées :

```text
Route
    -> protocole HTTP / webhook

Schémas
    -> représentation des données normalisées

Service WhatsApp
    -> parsing, orchestration et appels Meta

Chat service
    -> traitement conversationnel

Pipeline RAG
    -> intelligence métier
```

---

## Configuration WhatsApp

Les paramètres nécessaires sont chargés depuis la configuration centralisée.

Les variables utilisées sont :

```env
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_API_VERSION=
ENABLE_WHATSAPP=
```

Les valeurs réelles sont placées uniquement dans :

```text
.env
```

Elles ne doivent jamais être versionnées.

Le fichier :

```text
.env.example
```

conserve uniquement les noms des variables et des valeurs non sensibles.

---

## Feature flag WhatsApp

L'activation de l'intégration dépend de :

```text
ENABLE_WHATSAPP
```

Lorsque la fonctionnalité est désactivée, les routes WhatsApp ne doivent pas lancer le traitement normal.

Cette approche permet de conserver la même stratégie que pour les autres composants optionnels du backend.

---

## Isolation des tests de configuration

L'environnement local utilise désormais WhatsApp activé pour les tests réels.

Cela a révélé qu'un test utilisant directement :

```python
Settings()
```

pouvait récupérer les valeurs du fichier `.env` local.

Les tests des valeurs par défaut ont donc été isolés avec :

```python
Settings(
    _env_file=None,
)
```

Ainsi :

```text
Configuration réelle locale
        |
        X
        |
Tests des valeurs par défaut
```

Cette modification permet de garantir que les tests de configuration ne dépendent pas de l'environnement de la machine de développement.

---

## Vérification du webhook

Meta utilise une requête HTTP GET pour vérifier l'URL déclarée comme webhook.

La route exposée est :

```text
GET /api/v1/whatsapp/webhook
```

Meta transmet notamment :

```text
hub.mode
hub.verify_token
hub.challenge
```

Le backend vérifie :

```text
hub.mode == "subscribe"
```

ainsi que la correspondance entre :

```text
hub.verify_token
```

et :

```text
WHATSAPP_VERIFY_TOKEN
```

Lorsque la vérification réussit, le backend retourne :

```text
hub.challenge
```

avec :

```text
HTTP 200
```

Lorsque le token est invalide, la requête est refusée.

---

## Rôle du verify token

Le :

```text
WHATSAPP_VERIFY_TOKEN
```

est un secret défini par l'application.

Il permet à Meta et au backend de vérifier qu'ils utilisent la même configuration lors de l'enregistrement du webhook.

Il ne correspond pas :

```text
au numéro WhatsApp
au Phone Number ID
au WhatsApp Business Account ID
à l'Access Token Meta
```

Sa valeur réelle reste exclusivement dans `.env`.

---

## Réception des événements Meta

Les événements WhatsApp sont reçus par :

```text
POST /api/v1/whatsapp/webhook
```

La route :

```text
backend/app/api/routes/whatsapp.py
```

lit le payload JSON envoyé par Meta puis transmet son contenu au service WhatsApp.

Le webhook peut recevoir plusieurs types d'événements.

Par exemple :

```text
messages utilisateur
statuts de messages
notifications Meta
```

À ce stade de B8, seuls les messages texte utilisateur sont transmis au pipeline conversationnel.

Les autres événements sont acceptés sans déclencher de traitement texte.

---

## Schéma normalisé du message texte

Un schéma dédié a été créé :

```python
WhatsAppTextMessage
```

Il contient :

```text
sender
message_id
text
```

Le champ :

```text
sender
```

correspond au numéro WhatsApp de l'utilisateur.

Le champ :

```text
message_id
```

correspond à l'identifiant du message fourni par Meta.

Le champ :

```text
text
```

contient le corps du message utilisateur.

---

## Extraction des messages

La fonction :

```python
extract_text_messages(...)
```

analyse la structure du payload Meta.

Le parcours suit principalement :

```text
entry
  |
  v
changes
  |
  v
value
  |
  v
messages
```

Pour chaque message, le service vérifie notamment :

```text
message valide
type == text
sender présent
message_id présent
text.body présent
```

Lorsqu'une information obligatoire manque, le message est ignoré.

Cette approche permet d'éviter qu'un événement Meta incomplet ne provoque une erreur dans le pipeline conversationnel.

---

## Réponse immédiate au webhook

Meta attend une réponse HTTP rapide après l'envoi d'un webhook.

Le traitement conversationnel pouvant nécessiter :

```text
Agent
Retriever
Qdrant
Gemini
```

il ne doit pas bloquer inutilement la réponse HTTP adressée à Meta.

FastAPI utilise donc :

```python
BackgroundTasks
```

Le principe est :

```text
POST webhook
     |
     v
Validation JSON
     |
     v
Extraction message
     |
     +--------------------+
     |                    |
     v                    v
HTTP 200           BackgroundTasks
                          |
                          v
                 Traitement conversationnel
```

Cette organisation réduit le risque que Meta considère le webhook comme non disponible pendant une requête RAG plus longue.

---

## Traitement d'un message texte WhatsApp

La fonction :

```python
process_whatsapp_text_message(...)
```

reçoit un :

```python
WhatsAppTextMessage
```

puis appelle le service Chat existant.

Le principe est :

```python
process_chat(
    query=message.text,
    thread_id=message.sender,
)
```

WhatsApp ne possède donc pas son propre Agent ou son propre Retriever.

Il utilise directement les composants déjà intégrés au backend.

---

## Utilisation du numéro utilisateur comme thread_id

Le numéro WhatsApp de l'expéditeur est utilisé comme :

```text
thread_id
```

Le mécanisme devient :

```text
Numéro utilisateur
        |
        v
sender
        |
        v
thread_id
        |
        v
Conversation backend
```

Ce choix permet de disposer d'un identifiant stable entre plusieurs messages envoyés par le même utilisateur.

Il évite également de générer un nouveau `thread_id` pour chaque message WhatsApp.

---

## Flux conversationnel texte

Le flux applicatif complet pour un message texte est :

```text
Utilisateur
    |
    v
Message WhatsApp
    |
    v
Meta
    |
    v
POST /api/v1/whatsapp/webhook
    |
    v
extract_text_messages()
    |
    v
WhatsAppTextMessage
    |
    v
BackgroundTasks
    |
    v
process_whatsapp_text_message()
    |
    v
process_chat()
    |
    v
Agent
```

Selon l'intention détectée :

```text
Agent
 |
 +--> static
 |
 +--> clarify
 |
 +--> direct_llm
 |
 +--> rag
```

---

## Envoi d'un message vers WhatsApp

Le service expose la fonction :

```python
send_whatsapp_text_message(...)
```

Elle permet d'envoyer une réponse depuis le backend vers WhatsApp Cloud API.

L'appel utilise :

```text
https://graph.facebook.com/
```

avec :

```text
WHATSAPP_API_VERSION
```

et :

```text
WHATSAPP_PHONE_NUMBER_ID
```

pour construire l'endpoint correspondant au numéro WhatsApp Meta.

---

## Authentification Graph API

L'appel HTTP utilise :

```text
Authorization: Bearer <WHATSAPP_ACCESS_TOKEN>
```

Le token provient exclusivement de la configuration locale.

Il n'est jamais écrit directement dans le code source.

Le header JSON utilisé est :

```text
Content-Type: application/json
```

---

## Payload d'envoi texte

Le payload utilisé pour un message texte suit la structure :

```json
{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "<destinataire>",
  "type": "text",
  "text": {
    "preview_url": false,
    "body": "<réponse>"
  }
}
```

Le champ :

```text
to
```

correspond au numéro WhatsApp de l'utilisateur.

Le champ :

```text
body
```

contient la réponse conversationnelle produite par le backend.

---

## Réutilisation de ChatResponse

Après l'appel :

```python
chat_response = process_chat(...)
```

le service vérifie que le traitement est réussi et qu'une réponse est disponible.

Lorsque :

```text
chat_response.success = true
```

et que :

```text
chat_response.answer
```

est renseigné, la réponse est envoyée à WhatsApp.

Le flux devient :

```text
process_chat()
      |
      v
ChatResponse.answer
      |
      v
send_whatsapp_text_message()
      |
      v
Meta Graph API
      |
      v
Utilisateur
```

---

## Client HTTP

Les appels à Graph API utilisent :

```text
httpx
```

déjà présent dans les dépendances du backend.

La fonction d'envoi peut :

```text
créer son propre client HTTP
```

ou :

```text
recevoir un client injecté
```

Cette seconde possibilité facilite les tests automatisés sans appel réel à Meta.

---

## Tests automatisés de B8

Les tests de l'intégration WhatsApp sont regroupés dans :

```text
backend/tests/test_whatsapp.py
```

Ils couvrent actuellement :

```text
1. vérification correcte du webhook Meta

2. rejet d'un verify token incorrect

3. comportement lorsque WhatsApp est désactivé

4. extraction d'un message texte depuis un payload Meta

5. réception d'un webhook contenant un message texte

6. réception d'un événement sans message texte

7. utilisation du numéro utilisateur comme thread_id

8. planification du traitement dans BackgroundTasks

9. envoi d'un message texte via Graph API avec HTTP mocké
```

Le résultat ciblé obtenu est :

```text
9 passed
```

---

## Mock de Graph API

L'envoi HTTP est testé avec :

```python
httpx.MockTransport
```

Le test vérifie notamment :

```text
URL Graph API
Authorization Bearer
messaging_product
destinataire
type du message
contenu text.body
réponse Meta simulée
```

Cette approche évite :

```text
d'utiliser le vrai Access Token
d'envoyer un message réel
de dépendre du réseau
de consommer inutilement des appels Meta
```

pendant les tests automatisés.

---

## Validation de la suite backend

Après l'ajout des tests WhatsApp, la suite complète du backend a été exécutée.

Résultat :

```text
51 passed
```

Un warning lié à Starlette / AnyIO reste présent.

Il provient d'une dépendance externe utilisée par `TestClient` et ne bloque pas le fonctionnement du backend.

---

## Mise en place du numéro de test Meta

L'intégration a d'abord été configurée avec le numéro de test fourni dans l'environnement développeur Meta.

Les éléments nécessaires sont notamment :

```text
Temporary Access Token
Phone Number ID
WhatsApp Business Account
numéro destinataire autorisé
```

Le numéro personnel utilisé pour les essais doit être enregistré parmi les destinataires autorisés de l'environnement de test.

---

## Première erreur de destinataire

Lors d'un premier essai d'envoi, le numéro de test Meta avait été utilisé comme destinataire.

Graph API a retourné une erreur indiquant que le numéro destinataire n'était pas présent dans la liste autorisée.

Le problème ne provenait pas de la fonction d'envoi.

Le destinataire devait être le numéro utilisateur autorisé pour les tests.

Après correction, l'envoi réel a fonctionné.

---

## Validation réelle de l'envoi

Un message texte a été envoyé depuis le backend vers le numéro WhatsApp utilisateur autorisé.

Meta a retourné une réponse contenant un identifiant :

```text
wamid...
```

Le message a ensuite été reçu sur le téléphone.

Cette validation confirme le flux :

```text
Backend
   |
   v
Graph API
   |
   v
WhatsApp Cloud API
   |
   v
Téléphone utilisateur
```

La partie sortante de l'intégration est donc fonctionnelle.

---

## Exposition publique du backend local

Le backend étant exécuté sur :

```text
127.0.0.1:8000
```

Meta ne peut pas directement accéder à cette adresse locale.

Un tunnel HTTPS est donc nécessaire pendant le développement.

L'outil retenu est :

```text
cloudflared
```

---

## Installation de Cloudflare Tunnel

L'outil :

```text
cloudflared
```

a été installé sur la machine de développement.

Le tunnel est lancé avec :

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Cloudflare génère alors une URL publique temporaire :

```text
https://<identifiant>.trycloudflare.com
```

---

## Callback URL Meta

La Callback URL utilisée prend la forme :

```text
https://<tunnel>.trycloudflare.com/api/v1/whatsapp/webhook
```

Cette URL est enregistrée dans la configuration webhook de l'application Meta.

Le verify token configuré dans Meta doit correspondre à :

```text
WHATSAPP_VERIFY_TOKEN
```

du backend.

---

## Particularité du Quick Tunnel

Le Quick Tunnel utilisé pendant le développement est temporaire.

Lorsqu'il est arrêté puis relancé :

```text
ancienne URL
    |
    X
    |
nouvelle URL
```

Une nouvelle adresse `trycloudflare.com` est généralement générée.

La Callback URL Meta doit donc être mise à jour lorsqu'une nouvelle URL est utilisée.

Cette solution est suffisante pour les tests locaux mais n'est pas destinée à la production.

---

## Démarrage du backend pour les essais WhatsApp

Le serveur est lancé avec :

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

Le mode `--reload` n'est pas nécessaire pendant les essais impliquant Qdrant local.

Cette précaution évite de créer plusieurs processus pouvant tenter d'ouvrir simultanément le même stockage Qdrant.

---

## Validation publique du GET webhook

Après exposition avec Cloudflare, Meta a pu accéder à :

```text
GET /api/v1/whatsapp/webhook
```

Le challenge a été retourné correctement.

Le flux suivant a donc été validé :

```text
Meta
 |
 v
Internet
 |
 v
Cloudflare HTTPS
 |
 v
localhost
 |
 v
FastAPI
 |
 v
verify token
 |
 v
challenge
```

---

## Validation publique du POST webhook

Un POST vers l'URL publique a également été testé.

Le backend a retourné :

```text
status = received
```

sans erreur.

Cela confirme que :

```text
Meta / Internet
       |
       v
Tunnel Cloudflare
       |
       v
FastAPI POST webhook
```

est fonctionnel.

---

## Abonnement de l'application au WABA

La présence d'une Callback URL valide ne suffit pas à elle seule pour recevoir les messages.

L'application doit également être abonnée au :

```text
WhatsApp Business Account
```

L'abonnement a été vérifié puis effectué à travers :

```text
/{WABA_ID}/subscribed_apps
```

L'opération a retourné :

```json
{
  "success": true
}
```

---

## Abonnement au champ messages

Dans la configuration Meta, le champ :

```text
messages
```

a été activé pour le webhook.

Après configuration :

```text
Application
    |
    v
WABA
    |
    v
messages
    |
    v
Webhook
```

les messages entrants ont commencé à générer des requêtes POST vers le backend.

---

## Expiration du token temporaire

Pendant les essais, un token Meta temporaire a expiré.

Les appels Graph API ont alors retourné une erreur d'authentification.

Un nouveau token temporaire a été généré depuis l'environnement développeur Meta puis replacé dans :

```text
.env
```

Le backend a ensuite été redémarré afin de recharger la configuration.

Aucun token réel n'est enregistré dans la documentation ou dans Git.

---

## Validation réelle de la réception

Après la configuration du WABA, du champ `messages` et du webhook, un message envoyé depuis WhatsApp a atteint le backend.

Les logs ont montré des appels :

```text
POST /api/v1/whatsapp/webhook
```

avec :

```text
HTTP 200
```

La chaîne entrante est donc validée :

```text
Téléphone utilisateur
        |
        v
WhatsApp
        |
        v
Meta
        |
        v
Cloudflare
        |
        v
FastAPI
```

---

## Validation du thread_id réel

Lors du traitement d'un message WhatsApp réel, le numéro de l'expéditeur est transmis au service Chat comme :

```text
thread_id
```

Le principe défini dans les tests automatisés a donc également été observé dans l'intégration réelle.

Le flux est :

```text
sender WhatsApp
      |
      v
thread_id
      |
      v
process_chat()
```

---

## Validation des réponses statiques

Plusieurs types de requêtes simples ont permis de vérifier le passage dans l'Agent conversationnel.

Les routes observées comprennent notamment :

```text
greeting
capabilities
clarify
```

Ces traitements ne nécessitent pas systématiquement Gemini.

Une salutation envoyée depuis le téléphone a permis de valider la chaîne complète.

---

## Validation end-to-end du texte WhatsApp

La réponse statique générée par le backend a été renvoyée par WhatsApp Cloud API puis reçue sur le téléphone.

Le flux complet suivant est donc validé :

```text
Téléphone utilisateur
        |
        v
WhatsApp
        |
        v
Meta
        |
        v
Webhook
        |
        v
FastAPI
        |
        v
BackgroundTasks
        |
        v
process_chat()
        |
        v
Agent
        |
        v
Réponse
        |
        v
Graph API
        |
        v
WhatsApp
        |
        v
Téléphone utilisateur
```

Cette validation confirme que la partie texte de B8 fonctionne réellement de bout en bout.

---

## Test d'une requête météorologique

Une question météorologique a ensuite été envoyée depuis WhatsApp.

Les logs ont confirmé :

```text
route = rag
intent = meteo_generale
retrieval = true
```

Le Retriever hybride et Qdrant ont donc été atteints correctement.

La récupération documentaire s'est exécutée avant l'appel au modèle de génération.

---

## Diagnostic de la génération Gemini

La génération a ensuite retourné :

```text
service_unavailable
```

Afin de distinguer une erreur du pipeline d'une erreur du fournisseur LLM, un appel Gemini direct et indépendant a été effectué.

Résultat :

```text
SUCCESS = False
ERROR = service_unavailable
```

Le détail retourné était :

```text
503 UNAVAILABLE
```

avec une indication de forte demande temporaire sur le modèle.

Cette erreur confirme que :

```text
Webhook WhatsApp     : fonctionnel
process_chat         : fonctionnel
Agent                : fonctionnel
Retriever            : fonctionnel
Qdrant               : fonctionnel
appel Gemini         : atteint
service Gemini       : temporairement indisponible
```

L'erreur ne provenait donc pas de l'intégration WhatsApp.

---

## Classification des erreurs Gemini

La logique existante distingue notamment :

```text
429 -> rate_limit

503 -> service_unavailable
```

Le cas observé pendant les essais correspondait bien à :

```text
503 -> service_unavailable
```

Aucune modification du mapping d'erreurs n'a été nécessaire.

---

## Warning AFC Gemini

Pendant l'appel de génération, un warning lié à l'utilisation directe de l'Automatic Function Calling a également été affiché.

Ce warning n'a pas été identifié comme la cause de l'échec.

L'erreur réelle renvoyée par l'API reste :

```text
503 UNAVAILABLE
```

Le warning AFC est donc distinct de l'indisponibilité temporaire du service.

---

## État du token Meta pendant le développement

Le token utilisé actuellement pour les essais est temporaire.

Il permet :

```text
envoi de messages
appels Graph API
gestion des abonnements nécessaires aux tests
```

mais doit être renouvelé lorsqu'il expire.

Cette contrainte est acceptable pour la phase de développement actuelle.

Le passage à une authentification plus durable est volontairement reporté après l'intégration audio WhatsApp.

---

## État du tunnel pendant le développement

Le backend utilise actuellement un Quick Tunnel Cloudflare.

Cette solution permet de recevoir les webhooks Meta pendant les tests sans déployer immédiatement l'application sur un serveur distant.

Limite actuelle :

```text
redémarrage tunnel
      |
      v
nouvelle URL
      |
      v
mise à jour Callback URL Meta
```

La mise en place d'une URL stable est reportée après l'intégration audio.

---

## Portée de la validation actuelle

À ce stade, B8 permet déjà des interactions WhatsApp texte normales dans l'environnement de test Meta.

La chaîne suivante fonctionne :

```text
message texte utilisateur
        |
        v
webhook Meta
        |
        v
backend
        |
        v
Agent
        |
        v
réponse
        |
        v
WhatsApp utilisateur
```

Les limitations actuelles concernent principalement :

```text
token temporaire
URL Cloudflare temporaire
messages vocaux non encore intégrés
sécurité de production non finalisée
```

Ces limitations n'empêchent pas les tests fonctionnels texte.

---

## Sécurité actuelle

Les secrets WhatsApp restent dans :

```text
.env
```

et ne doivent jamais être affichés dans :

```text
logs
tests
documentation
commits Git
```

Les fichiers de configuration versionnés ne doivent contenir que des valeurs neutres.

Les éléments concernés sont notamment :

```text
WHATSAPP_ACCESS_TOKEN
WHATSAPP_VERIFY_TOKEN
Phone Number ID réel
autres identifiants sensibles Meta
```

---

## Points restant à renforcer

Certaines améliorations sont volontairement reportées après l'intégration audio.

Elles concernent notamment :

```text
token Meta durable
URL webhook stable
gestion des doublons de message
validation de signature webhook
durcissement de la gestion des erreurs
finalisation des logs WhatsApp
```

Ces éléments correspondent à la phase de stabilisation de B8 et non au premier fonctionnement du canal texte.

---

## Tests B8 actuellement validés

La phase B8 a été développée progressivement afin de valider séparément le canal texte, la réception audio, puis la réponse vocale complète.

### Évolution des tests WhatsApp

La première version fonctionnelle du canal texte disposait de :

```text
9 tests WhatsApp validés
```

L'intégration progressive de la réception des messages vocaux et des opérations sur les médias Meta a ensuite porté la suite de tests à :

```text
15 tests WhatsApp validés
```

Les fonctions nécessaires à la réponse vocale ont ensuite été ajoutées et testées séparément :

```text
16 tests : ajout de la conversion WAV -> OGG/Opus
17 tests : ajout de l'upload d'un média vers Meta
18 tests : ajout de l'envoi d'un message audio WhatsApp
19 tests : ajout du fallback texte en cas d'échec de la chaîne audio sortante
```

La commande de validation ciblée finale est :

```powershell
python -m pytest backend/tests/test_whatsapp.py -q
```

Résultat final :

```text
19 passed
```

Les tests complets du backend ont ensuite été exécutés :

```powershell
python -m pytest backend/tests -q
```

Résultat :

```text
61 passed, 1 warning
```

Le contrôle de cohérence Git a également été exécuté :

```powershell
git diff --check
```

Aucune erreur de formatage n'a été signalée.

---

## Extension du webhook aux messages vocaux

Le webhook B8 prend désormais en charge deux types de messages entrants :

```text
message texte
message audio
```

Lorsqu'un message audio est reçu, le webhook extrait notamment :

```text
numéro de l'expéditeur
identifiant du message
identifiant du média Meta
type MIME du média
```

Ces informations sont représentées par le schéma :

```text
WhatsAppAudioMessage
```

Le numéro WhatsApp de l'utilisateur reste utilisé comme `thread_id`, ce qui permet de conserver la même logique de continuité conversationnelle que pour les messages texte.

---

## Récupération des médias audio Meta

Un message vocal reçu par le webhook ne contient pas directement les données binaires du fichier audio.

La récupération est réalisée en deux étapes :

```text
media_id
   |
   v
récupération des métadonnées Meta
   |
   v
URL temporaire du média
   |
   v
téléchargement authentifié du contenu audio
```

Deux fonctions dédiées sont utilisées :

```text
get_whatsapp_media_metadata()
download_whatsapp_media()
```

Le média téléchargé est enregistré dans un fichier temporaire avant d'être transmis à la couche audio développée en B7.

Les fichiers temporaires sont supprimés à la fin du traitement.

---

## Validation réelle de la réception audio

La chaîne de réception a été testée avec un véritable message vocal envoyé depuis WhatsApp.

Le premier essai de récupération du média a retourné une erreur d'authentification HTTP `401`.

L'analyse a montré que le token Meta utilisé n'était plus valide pour la récupération du média.

Après renouvellement de l'authentification, la récupération du média a fonctionné.

Un second problème de configuration a ensuite été détecté lors de l'envoi de la réponse :

```text
WHATSAPP_PHONE_NUMBER_ID manquant
```

La configuration locale a été corrigée sans exposer les secrets dans le dépôt Git.

Après ces corrections, le flux réel suivant a été validé :

```text
message vocal WhatsApp
        |
        v
webhook Meta
        |
        v
media_id
        |
        v
métadonnées du média
        |
        v
téléchargement audio
        |
        v
pipeline audio B7
        |
        v
réponse texte WhatsApp
```

Cette étape a permis de valider la réception des vocaux avant l'intégration de la réponse vocale.

---

## Stabilisation de l'authentification Meta

Les premiers essais ont utilisé un token temporaire fourni par l'environnement de test Meta.

Ce mécanisme n'étant pas adapté à une utilisation durable, la configuration a ensuite été associée à un System User disposant des ressources WhatsApp nécessaires.

Un token destiné à un usage durable a alors été configuré localement.

Les informations sensibles restent exclusivement dans l'environnement local et ne doivent pas être ajoutées au dépôt Git.

Les éléments suivants ne doivent notamment jamais être versionnés :

```text
access token Meta
verify token privé
identifiants sensibles
fichier .env
```

---

## Réutilisation de la couche audio B7

La prise en charge audio de WhatsApp ne recrée pas de logique Speech-to-Text ou Text-to-Speech spécifique dans `whatsapp_service.py`.

Elle réutilise directement :

```text
audio_service.process_audio_chat()
```

Pour une interaction vocale WhatsApp, l'appel utilise désormais :

```text
output_mode="audio"
```

ainsi qu'un chemin explicite pour le fichier audio généré :

```text
audio_output_path=<fichier WAV temporaire>
```

La responsabilité des composants reste ainsi séparée.

### Couche B7

```text
audio utilisateur
        |
        v
Speech-to-Text
        |
        v
pipeline conversationnel
        |
        v
réponse textuelle
        |
        v
Text-to-Speech
        |
        v
WAV
```

### Couche B8

```text
WAV
 |
 v
conversion WhatsApp
 |
 v
upload Meta
 |
 v
envoi du vocal
```

Cette séparation évite de dupliquer les traitements audio déjà développés et testés dans B7.

---

## Format audio de sortie

La synthèse vocale de B7 produit un fichier WAV.

Pour l'envoi d'un message vocal WhatsApp, une étape de conversion a été ajoutée afin de produire un fichier OGG utilisant le codec Opus.

La fonction dédiée est :

```text
convert_wav_to_whatsapp_ogg()
```

Le traitement repose sur FFmpeg avec `libopus`.

La chaîne de conversion est :

```text
WAV
 |
 v
FFmpeg
 |
 v
libopus
 |
 v
OGG/Opus
```

La configuration utilisée produit un flux mono adapté à la voix.

---

## Installation et validation de FFmpeg

FFmpeg n'était pas initialement disponible dans l'environnement local.

Il a été installé sur la machine de développement, puis sa disponibilité a été contrôlée avec :

```powershell
ffmpeg -version
```

La version installée dispose du support :

```text
libopus
```

Un premier test local de conversion a été effectué avec un fichier WAV contenant une tonalité synthétique.

Ce fichier avait uniquement pour objectif de tester :

```text
création du WAV
conversion FFmpeg
création du conteneur OGG
codec Opus
lecture du fichier obtenu
```

Il ne contenait volontairement aucune parole.

Le résultat de conversion a ensuite été inspecté et le fichier OGG/Opus produit a été validé.

---

## Validation réelle de la synthèse vocale

Après la validation technique de la conversion, la synthèse vocale réelle de B7 a été testée séparément.

Le pipeline TTS a produit un fichier WAV contenant une phrase parlée.

Les contrôles réalisés ont confirmé :

```text
génération TTS réussie
fichier WAV créé
fichier non vide
audio audible
phrase synthétisée correctement
```

Cela a permis de distinguer clairement :

```text
test technique avec tonalité
        !=
test réel de synthèse vocale
```

---

## Upload des médias vers Meta

Une fonction dédiée permet d'envoyer le fichier OGG généré vers l'API Meta :

```text
upload_whatsapp_media()
```

Le flux est :

```text
fichier OGG/Opus local
        |
        v
POST média Meta
        |
        v
media_id
```

La fonction a d'abord été validée avec un client HTTP simulé afin de vérifier :

```text
endpoint utilisé
authentification
multipart
messaging_product
fichier envoyé
type MIME
récupération du media_id
```

Un test réel a ensuite confirmé que Meta acceptait effectivement le fichier OGG et retournait un identifiant média valide.

---

## Envoi d'un message vocal WhatsApp

L'envoi d'un média audio déjà chargé sur Meta est assuré par :

```text
send_whatsapp_audio_message()
```

La fonction transmet notamment :

```text
destinataire
media_id
type audio
voice=True
```

Elle a d'abord été testée avec un client HTTP simulé.

Un test réel a ensuite permis de confirmer :

```text
upload média réussi
media_id obtenu
requête d'envoi acceptée
message_id retourné
audio reçu sur WhatsApp
```

Le premier fichier utilisé pour ce test contenait uniquement la tonalité synthétique servant au contrôle du transport.

Le fait qu'aucune parole ne soit présente dans ce fichier était donc attendu et ne constituait pas une erreur de la chaîne WhatsApp.

---

## Validation d'un véritable vocal synthétisé

Après validation séparée du TTS et de la chaîne Meta, un véritable fichier WAV généré par B7 a été utilisé.

Le flux réel testé a été :

```text
TTS B7
  |
  v
WAV
  |
  v
conversion OGG/Opus
  |
  v
upload Meta
  |
  v
media_id
  |
  v
envoi WhatsApp
  |
  v
smartphone
```

Les contrôles ont confirmé :

```text
conversion réussie
upload réussi
envoi réussi
message_id présent
vocal reçu sur WhatsApp
phrase audible et correcte
```

La chaîne audio sortante était donc validée avant son intégration automatique au webhook.

---

## Intégration automatique audio vers audio

La fonction :

```text
process_whatsapp_audio_message()
```

a ensuite été étendue afin d'utiliser automatiquement le mode audio de B7.

Le flux final est désormais :

```text
message vocal utilisateur
        |
        v
webhook WhatsApp
        |
        v
media_id
        |
        v
récupération des métadonnées
        |
        v
téléchargement du média
        |
        v
fichier audio entrant temporaire
        |
        v
audio_service.process_audio_chat()
        |
        | output_mode="audio"
        |
        v
Speech-to-Text
        |
        v
pipeline conversationnel
        |
        v
Text-to-Speech
        |
        v
WAV temporaire
        |
        v
convert_wav_to_whatsapp_ogg()
        |
        v
OGG/Opus temporaire
        |
        v
upload_whatsapp_media()
        |
        v
media_id
        |
        v
send_whatsapp_audio_message()
        |
        v
réponse vocale WhatsApp
```

Le numéro de l'expéditeur est transmis comme :

```text
thread_id
```

ce qui permet de conserver le contexte conversationnel par utilisateur.

---

## Fallback texte

La génération d'une réponse textuelle et sa synthèse vocale sont deux opérations distinctes.

Il est donc possible que le pipeline conversationnel produise correctement une réponse alors qu'une étape ultérieure de la chaîne audio échoue.

Un mécanisme de fallback a été ajouté.

Si une erreur intervient notamment pendant :

```text
conversion WAV -> OGG/Opus
upload du média
envoi du vocal
```

et qu'une réponse textuelle est disponible, celle-ci peut être envoyée à l'utilisateur via :

```text
send_whatsapp_text_message()
```

Le comportement testé est :

```text
réponse conversationnelle disponible
        |
        v
échec chaîne audio sortante
        |
        v
fallback texte
        |
        v
réponse WhatsApp conservée
```

Un test spécifique valide ce scénario.

---

## Gestion des fichiers temporaires

Le traitement d'un message vocal peut créer jusqu'à trois fichiers temporaires :

```text
audio entrant téléchargé
WAV produit par le TTS
OGG/Opus destiné à WhatsApp
```

Ces fichiers sont utilisés uniquement pendant la durée du traitement.

La fonction assure leur suppression dans son bloc de nettoyage, y compris après le traitement nominal.

Les tests contrôlent notamment que les chemins temporaires n'existent plus après exécution.

---

## Validation end-to-end réelle audio vers audio

Après validation des composants isolés et des tests automatisés, un test réel a été effectué depuis un téléphone WhatsApp.

Le flux testé était :

```text
utilisateur
   |
   | message vocal
   v
WhatsApp
   |
   v
Meta Cloud API
   |
   v
webhook HTTPS
   |
   v
backend
   |
   v
téléchargement audio
   |
   v
STT
   |
   v
pipeline conversationnel
   |
   v
TTS
   |
   v
WAV
   |
   v
OGG/Opus
   |
   v
upload Meta
   |
   v
réponse vocale WhatsApp
   |
   v
utilisateur
```

Les validations réalisées ont confirmé :

```text
webhook reçu correctement
traitement backend exécuté
réponse vocale reçue
audio audible
réponse correcte
aucune erreur bloquante dans le terminal
```

L'interaction WhatsApp audio vers audio est donc fonctionnelle de bout en bout dans l'environnement de développement actuel.

---

## Tunnel HTTPS de développement

Les tests réels utilisent actuellement Cloudflare Tunnel afin d'exposer temporairement le serveur FastAPI local à Meta.

Le tunnel est lancé avec :

```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```

Lors d'un essai, plusieurs tentatives de connexion QUIC ont temporairement échoué avant que Cloudflare établisse finalement la connexion :

```text
Registered tunnel connection
protocol=quic
```

Le webhook est alors accessible publiquement via l'URL HTTPS générée.

Cette solution est adaptée aux essais de développement, mais le Quick Tunnel utilisé actuellement ne constitue pas une URL stable de production.

À chaque changement d'URL, la Callback URL configurée côté Meta doit être mise à jour.

---

## Architecture B8 finale validée

```text
                         Utilisateur WhatsApp
                                  |
                    +-------------+-------------+
                    |                           |
                 texte                        vocal
                    |                           |
                    v                           v
              Webhook Meta                Webhook Meta
                    |                           |
                    v                           v
       extract_text_messages()      extract_audio_messages()
                    |                           |
                    v                           v
        WhatsAppTextMessage          WhatsAppAudioMessage
                    |                           |
                    v                           v
           BackgroundTasks                media_id
                    |                           |
                    |                           v
                    |                 métadonnées Meta
                    |                           |
                    |                           v
                    |                  téléchargement
                    |                           |
                    |                           v
                    |                    audio temporaire
                    |                           |
                    |                           v
                    |                process_audio_chat()
                    |                           |
                    |                       STT / TTS
                    |                           |
                    |                           v
                    |                          WAV
                    |                           |
                    |                           v
                    |                      OGG/Opus
                    |                           |
                    v                           v
             process_chat()              upload Meta
                    |                           |
                    v                           v
              Agent / RAG                   media_id
                    |                           |
                    v                           v
          réponse textuelle           envoi vocal WhatsApp
                    |                           |
                    +-------------+-------------+
                                  |
                                  v
                         Utilisateur WhatsApp
```

---

## État final de B8 avant stabilisation

```text
Configuration WhatsApp locale             : validée
Feature flag                               : validé
Webhook GET                                : validé
Webhook POST                               : validé
Verify token                               : validé
Parsing texte                              : validé
Parsing audio                              : validé
WhatsAppTextMessage                        : validé
WhatsAppAudioMessage                       : validé
BackgroundTasks                            : validé
Numéro utilisateur comme thread_id         : validé
Connexion au pipeline conversationnel      : validée
Envoi texte Graph API                      : validé
Récupération métadonnées média             : validée
Téléchargement média                       : validé
Connexion à la couche audio B7             : validée
Speech-to-Text                             : validé
Text-to-Speech                             : validé
Production WAV                             : validée
FFmpeg                                     : validé
libopus                                    : validé
Conversion WAV -> OGG/Opus                 : validée
Upload média Meta                          : validé
Envoi audio WhatsApp                       : validé
voice=True                                 : validé
Fallback texte                             : validé
Nettoyage fichiers temporaires             : validé
Token Meta destiné à un usage durable      : configuré
Interaction texte end-to-end réelle        : validée
Réception vocale réelle                    : validée
Sortie vocale réelle                       : validée
Interaction audio -> audio end-to-end      : validée
Tests WhatsApp                             : 19 passed
Tests backend                              : 61 passed, 1 warning
git diff --check                           : validé
```
---

## Déduplication des messages WhatsApp

Afin d'éviter le retraitement d'un même événement lorsque Meta transmet plusieurs fois un webhook contenant le même message, un mécanisme d'idempotence a été ajouté.

Chaque message texte ou audio possède déjà un identifiant Meta unique :

```text
message_id
```

Avant de programmer son traitement en arrière-plan, le webhook vérifie désormais si cet identifiant a déjà été rencontré.

Le fonctionnement est :

```text
message reçu
    |
    v
message_id
    |
    v
registre temporaire
    |
    +--> déjà présent -> message ignoré
    |
    +--> nouveau -> enregistrement puis BackgroundTask
```

Le registre est maintenu en mémoire avec une durée de validité limitée afin d'éviter une croissance indéfinie. Un verrou protège l'opération de vérification et d'enregistrement contre des traitements concurrents.

La déduplication intervient avant les traitements coûteux. Elle évite notamment, pour un même vocal :

```text
téléchargement média répété
STT répété
génération conversationnelle répétée
TTS répété
conversion audio répétée
upload Meta répété
double réponse à l'utilisateur
```

Cette solution est adaptée à l'environnement actuel utilisant un seul processus applicatif. Dans un déploiement distribué ou multi-instance, le registre en mémoire devra être remplacé par un stockage partagé, par exemple Redis ou une base persistante.

Les tests automatisés couvrent :

```text
premier message accepté
même message texte reçu deux fois
même message audio reçu deux fois
```

Résultats après intégration :

```text
Tests WhatsApp : 22 passed
Tests backend  : 64 passed
```

---

## Éléments de stabilisation restant à traiter

Le fonctionnement fonctionnel de B8 est validé.

Les éléments suivants relèvent désormais du durcissement et de la préparation à un environnement plus stable :

```text
URL webhook permanente
gestion des doublons de messages
validation de signature du webhook
durcissement de la gestion des erreurs
finalisation des logs spécifiques WhatsApp
revue finale de sécurité
```

Le Quick Tunnel Cloudflare actuellement utilisé doit notamment être remplacé par une solution disposant d'une URL stable avant un déploiement durable.

Ces éléments ne remettent pas en cause la validation fonctionnelle des flux texte et audio obtenue pendant B8.

---

## Statut B8

```text
WhatsApp texte                 : VALIDÉ

WhatsApp audio entrant         : VALIDÉ

WhatsApp audio sortant         : VALIDÉ

WhatsApp audio -> audio        : VALIDÉ

Fallback texte                 : VALIDÉ

Tests automatisés              : VALIDÉS

Validation réelle sur téléphone: VALIDÉE

Stabilisation / durcissement   : À FINALISER
```

**Statut fonctionnel B8 : VALIDÉ**

**Statut global B8 : EN FINALISATION**