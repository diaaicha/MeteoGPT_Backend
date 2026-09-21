# Commandes utiles — MeteoGPT Backend

Ce document regroupe les commandes courantes utilisées pendant le développement
du backend MeteoGPT sous Windows avec PowerShell.

Il sert de mémo rapide lors de l'ouverture de VS Code ou d'une nouvelle session
de développement.

---

# 1. Se placer dans le projet

Le terminal doit être positionné à la racine du dépôt :

```powershell
cd "C:\Users\diaai\Documents\PFE ANACIM\MeteoGPT\MeteoGPT_Backend"
```

Vérification :

```powershell
Get-Location
```

Le chemin doit se terminer par :

```text
MeteoGPT_Backend
```

---

# 2. Activer l'environnement virtuel

Si PowerShell bloque l'exécution des scripts dans la session :

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Cette commande autorise temporairement les scripts uniquement dans le terminal
actuel.

Activer ensuite l'environnement Python du projet :

```powershell
.\.venv\Scripts\Activate.ps1
```

Lorsque l'environnement est actif, le terminal doit commencer par :

```text
(.venv)
```

Exemple :

```text
(.venv) PS C:\...\MeteoGPT_Backend>
```

---

# 3. Vérifier Python

Afficher la version utilisée :

```powershell
python --version
```

Version attendue :

```text
Python 3.11.9
```

Vérifier l'exécutable utilisé :

```powershell
python -c "import sys; print(sys.executable)"
```

Il doit pointer vers :

```text
MeteoGPT_Backend\.venv\Scripts\python.exe
```

---

# 4. Installer les dépendances

À utiliser après un nouveau clone du projet ou après modification des
dépendances :

```powershell
python -m pip install -r requirements-dev.txt
```

Afficher les packages installés :

```powershell
python -m pip list
```

---

# 5. Démarrer le backend FastAPI

Lancer le serveur de développement :

```powershell
python -m uvicorn backend.app.main:app --reload
```

Le backend devient accessible à :

```text
http://127.0.0.1:8000
```

`--reload` redémarre automatiquement le serveur lorsqu'un fichier Python est
modifié.

---

# 6. Arrêter FastAPI

Dans le terminal où Uvicorn fonctionne :

```text
Ctrl + C
```

Cette commande arrête le serveur local.

---

# 7. Routes disponibles

## Vérification du backend

```text
http://127.0.0.1:8000/health
```

Réponse attendue :

```json
{
  "status": "ok",
  "service": "MeteoGPT Backend",
  "environment": "development"
}
```

---

## Swagger

```text
http://127.0.0.1:8000/docs
```

Swagger permet de :

- consulter les endpoints disponibles ;
- voir les paramètres attendus ;
- exécuter directement des requêtes HTTP ;
- consulter les réponses de l'API.

---

## ReDoc

```text
http://127.0.0.1:8000/redoc
```

Affiche une documentation alternative de l'API.

---

## OpenAPI

```text
http://127.0.0.1:8000/openapi.json
```

Retourne la description OpenAPI complète de l'application.

---

## Route racine

```text
http://127.0.0.1:8000/
```

Aucune route racine n'est actuellement définie.

Une réponse :

```json
{
  "detail": "Not Found"
}
```

est donc normale.

---

# 8. Lancer tous les tests

Exécuter tous les tests du backend :

```powershell
pytest backend/tests -v
```

Version plus courte :

```powershell
pytest backend/tests -q
```

---

# 9. Lancer un fichier de test précis

Tests de configuration :

```powershell
pytest backend/tests/test_config.py -v
```

Tests FastAPI / Health :

```powershell
pytest backend/tests/test_health.py -v
```

---

# 10. Afficher la branche Git actuelle

```powershell
git branch --show-current
```

Permet de vérifier sur quelle branche le développement est effectué.

Il est recommandé de toujours vérifier la branche avant de commencer une
nouvelle modification.

---

# 11. Voir l'état du dépôt

```powershell
git status
```

Version compacte :

```powershell
git status --short
```

Cette commande permet de voir :

- les fichiers modifiés ;
- les nouveaux fichiers ;
- les fichiers supprimés ;
- les fichiers déjà préparés pour un commit.

---

# 12. Voir les dernières versions

```powershell
git log --oneline -10
```

Affiche les dix derniers commits.

Pour cinq commits :

```powershell
git log --oneline -5
```

---

# 13. Récupérer la dernière version de `develop`

Se placer sur `develop` :

```powershell
git checkout develop
```

Récupérer la dernière version distante :

```powershell
git pull origin develop
```

À faire avant de créer une nouvelle branche de développement.

---

# 14. Créer une nouvelle branche

Exemple :

```powershell
git checkout -b feature/b4-chat-rag
```

Puis créer la branche distante :

```powershell
git push -u origin feature/b4-chat-rag
```

Après cette première commande `push`, les prochains envois pourront simplement
utiliser :

```powershell
git push
```

---

# 15. Ajouter les modifications à Git

Ajouter un fichier précis :

```powershell
git add chemin/du/fichier
```

Exemple :

```powershell
git add backend/app/main.py
```

Ajouter plusieurs fichiers :

```powershell
git add backend
```

Ajouter toutes les modifications du projet :

```powershell
git add .
```

`git add .` doit être utilisé uniquement après avoir vérifié :

```powershell
git status --short
```

afin d'éviter d'ajouter involontairement des fichiers inutiles.

---

# 16. Créer un commit

Exemple :

```powershell
git commit -m "feat: add chat endpoint"
```

Préfixes utilisés dans le projet :

```text
feat:   nouvelle fonctionnalité
fix:    correction
docs:   documentation
test:   ajout ou modification de tests
chore:  configuration ou maintenance
refactor: restructuration sans changement fonctionnel
```

---

# 17. Envoyer une branche sur GitHub

```powershell
git push
```

Si la branche distante n'existe pas encore :

```powershell
git push -u origin nom-de-la-branche
```

---

# 18. Fusionner une feature dans `develop`

Après validation complète d'une phase :

```powershell
git checkout develop
```

Puis :

```powershell
git pull origin develop
```

Fusionner la branche :

```powershell
git merge --no-ff nom-de-la-branche -m "merge: description"
```

Exemple :

```powershell
git merge --no-ff feature/b3-fastapi-core -m "merge: complete B3 FastAPI core"
```

Puis envoyer `develop` :

```powershell
git push origin develop
```

---

# 19. Vérifier qu'un fichier est ignoré par Git

Exemple pour `.env` :

```powershell
git check-ignore -v .env
```

Exemple pour `.venv` :

```powershell
git check-ignore -v .venv/
```

Si une règle du `.gitignore` apparaît, le fichier est correctement ignoré.

---

# 20. Vérifier la configuration MeteoGPT

Afficher l'environnement :

```powershell
python -c "from backend.app.core.config import get_settings; print(get_settings().app_env)"
```

Résultat attendu :

```text
development
```

Afficher la racine du projet :

```powershell
python -c "from backend.app.core.config import PROJECT_ROOT; print(PROJECT_ROOT)"
```

Afficher le chemin Qdrant :

```powershell
python -c "from backend.app.core.config import get_settings; print(get_settings().absolute_qdrant_path)"
```

---

# 21. Vérifier les dépendances principales

```powershell
python -c "import fastapi, uvicorn, pydantic, pydantic_settings, httpx, pytest; print('BACKEND ENVIRONMENT OK')"
```

Résultat attendu :

```text
BACKEND ENVIRONMENT OK
```

---

# 22. Routine recommandée à l'ouverture de VS Code

À chaque nouvelle session de développement :

```powershell
cd "C:\Users\diaai\Documents\PFE ANACIM\MeteoGPT\MeteoGPT_Backend"

Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

.\.venv\Scripts\Activate.ps1

git branch --show-current

git status --short
```

Ensuite, selon le travail à effectuer :

```powershell
python -m uvicorn backend.app.main:app --reload
```

ou :

```powershell
pytest backend/tests -v
```

---

# 23. Routine avant un commit

Avant chaque commit :

```powershell
git branch --show-current
git status --short
pytest backend/tests -q
```

Si tous les tests passent :

```powershell
git add ...
git status
git commit -m "type: description"
git push
```

---

# 24. Routine de fin d'une phase B

Lorsqu'une phase est entièrement validée :

```text
1. Vérifier les tests
2. Vérifier git status
3. Commit de la feature
4. Push de la feature
5. Checkout develop
6. Pull develop
7. Merge de la feature
8. Push develop
9. Ajouter la documentation Markdown
10. Créer la branche de la phase suivante
```

---

# 25. Commandes rapides

| Besoin | Commande |
|---|---|
| Activer `.venv` | `.\.venv\Scripts\Activate.ps1` |
| Vérifier Python | `python --version` |
| Démarrer FastAPI | `python -m uvicorn backend.app.main:app --reload` |
| Arrêter FastAPI | `Ctrl + C` |
| Tous les tests | `pytest backend/tests -v` |
| Tests rapides | `pytest backend/tests -q` |
| Branche actuelle | `git branch --show-current` |
| État Git | `git status --short` |
| Historique Git | `git log --oneline -10` |
| Envoyer vers GitHub | `git push` |
| Swagger | `http://127.0.0.1:8000/docs` |
| Health | `http://127.0.0.1:8000/health` |
| OpenAPI | `http://127.0.0.1:8000/openapi.json` |






## B5 — Logs et observabilité

### Consulter les derniers logs

```powershell
Get-Content .\logs\meteogpt_backend.log -Tail 20
```

### Suivre les logs en temps réel

```powershell
Get-Content .\logs\meteogpt_backend.log -Wait
```

### Tester l’observabilité

```powershell
pytest .\backend\tests\test_observability.py -q
```

### Tester le Chat

```powershell
pytest .\backend\tests\test_chat.py -q
```

### Tester tout le backend

```powershell
pytest .\backend\tests -q
```

Résultat attendu après B5 :

```text
22 passed
```

### Vérifier la compilation des fichiers B5

```powershell
python -m py_compile `
    .\generation.py `
    .\backend\app\main.py `
    .\backend\app\core\logging.py `
    .\backend\app\core\log_context.py `
    .\backend\app\middleware\request_logging.py `
    .\backend\app\services\chat_service.py
```

### Tester le `request_id` sans appeler Gemini

```powershell
python -c "from fastapi.testclient import TestClient; from backend.app.main import app; r=TestClient(app).get('/health'); print('STATUS =', r.status_code); print('REQUEST_ID =', r.headers.get('X-Request-ID'))"
```

### Vérifier les modifications Git

```powershell
git status --short
```

```powershell
git diff --check
```

```powershell
git diff --stat
```

```powershell
git diff --name-only
```

### Vérifier la branche courante

```powershell
git branch --show-current
```

Branche attendue pour B5 :

```text
feature/b5-observability
```



---

# 26. Évolution du document

Ce fichier doit être complété lorsque de nouvelles commandes deviennent utiles.

Par exemple, après les prochaines phases, il pourra recevoir les commandes
associées à :

```text
RAG
Qdrant
actualisation ANACIM
audio
WhatsApp Cloud API
tests d'intégration
```

L'objectif est que ce document reste le point de référence rapide pour travailler
sur MeteoGPT sans devoir rechercher les commandes utilisées lors des phases
précédentes.



QUESTIONS TEST RAG

python -c "from datetime import datetime; from zoneinfo import ZoneInfo; from rag_pipeline import process_text_request; r=process_text_request('Que montre cette image météo pour Dakar ? Donne-moi les températures qui y sont indiquées.', thread_id='backend-b4-real-multimodal', now=datetime(2026,9,17,17,0,tzinfo=ZoneInfo('Africa/Dakar'))); print(r)"

python -c "from datetime import datetime; from zoneinfo import ZoneInfo; from rag_pipeline import process_text_request; r=process_text_request('En regardant le visuel météo, quelles températures sont indiquées pour Dakar ?', thread_id='backend-b4-multimodal-post-migration', now=datetime(2026,9,17,17,0,tzinfo=ZoneInfo('Africa/Dakar'))); print(r)"

python -c "from datetime import datetime; from zoneinfo import ZoneInfo; from rag_pipeline import process_text_request; r=process_text_request('Quel temps est prévu à Dakar ?', thread_id='backend-b4-post-migration', now=datetime(2026,9,17,17,0,tzinfo=ZoneInfo('Africa/Dakar'))); print(r)"
