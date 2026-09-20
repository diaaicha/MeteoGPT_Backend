# MeteoGPT Backend

Backend applicatif du projet MeteoGPT.

Ce dépôt est indépendant du dépôt expérimental contenant le notebook utilisé
durant la phase de conception, de développement et d'évaluation du système RAG.

## Objectif

Le backend a pour objectif d'exposer les composants intelligents validés de
MeteoGPT sous forme d'API et de permettre leur utilisation à travers différents
canaux, notamment WhatsApp.

## Composants principaux

MeteoGPT s'appuie sur :

- un Agent basé sur LangGraph ;
- un Retriever hybride Dense + BM25 + RRF enrichi par métadonnées ;
- une génération RAG contrôlée ;
- un module Speech-to-Text / Text-to-Speech ;
- un pipeline d'actualisation des données ANACIM.

## Stack backend

- Python 3.11
- FastAPI
- Uvicorn
- Pydantic
- LangGraph
- Qdrant local
- multilingual-e5-base
- Gemini API
- WhatsApp Cloud API Meta

## Environnement

Le projet est actuellement développé dans un environnement local de
développement dans le cadre d'un Projet de Fin d'Études.

Il ne s'agit pas encore d'un environnement de production.

## WhatsApp

L'intégration utilise directement la WhatsApp Cloud API officielle de Meta.

Twilio n'est pas utilisé.

## Principe architectural

Le backend ne réimplémente pas la logique RAG.

Il expose les modules intelligents validés :

Agent → Retriever → Generation

à travers une API FastAPI.



## Environnement de développement

Le backend MeteoGPT est développé avec Python 3.11 dans un environnement
virtuel local.

### Création de l'environnement

```bash
py -3.11 -m venv .venv