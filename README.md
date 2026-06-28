# SentimentAI — Pipeline DevOps complet

API d'analyse de sentiment (FastAPI) servant de fil rouge à un pipeline DevOps de niveau production :
**Git → Docker → Jenkins → SonarQube → Trivy → Registry → Terraform → Monitoring**.

Projet réalisé dans le cadre du module *DevOps — Project Management & Ability*, Mastère 1 DWM, ESTIAM Paris.

---

## Sommaire

- [Aperçu](#aperçu)
- [Architecture](#architecture)
- [Stack technique](#stack-technique)
- [Structure du dépôt](#structure-du-dépôt)
- [Démarrage rapide](#démarrage-rapide)
- [API](#api)
- [Observabilité](#observabilité)
- [Infrastructure as Code](#infrastructure-as-code)
- [Pipeline CI/CD](#pipeline-cicd)
- [Progression des TP](#progression-des-tp)
- [Auteur](#auteur)

---

## Aperçu

**SentimentAI** expose une API REST qui analyse le sentiment d'un texte et renvoie un label
(`POSITIVE` / `NEGATIVE` / `NEUTRAL`) accompagné d'un score de confiance. Au-delà de l'application
elle-même, le projet met en place toute la chaîne d'outillage DevOps autour d'un même artefact :
versionnement, conteneurisation, intégration continue, analyse qualité et sécurité, provisionnement
déclaratif de l'infrastructure et observabilité temps réel.

## Architecture

```
                   ┌──────────────┐      push       ┌──────────────────────┐
   Développeur ───▶│   GitHub     │────────────────▶│       Jenkins        │
                   │ sentiment-ai │   (Poll SCM)    │  Pipeline as Code    │
                   └──────────────┘                 └──────────┬───────────┘
                                                               │
            ┌──────────────────────────────────────────────────┤
            ▼                ▼               ▼                  ▼
      ┌───────────┐   ┌────────────┐   ┌──────────┐     ┌─────────────┐
      │   Lint    │   │ Build &    │   │ SonarQube│     │   Trivy     │
      │  flake8   │   │  Test      │   │ + Quality│     │  Scan CVE   │
      │           │   │  pytest    │   │   Gate   │     │             │
      └───────────┘   └─────┬──────┘   └──────────┘     └─────────────┘
                            │ docker push
                            ▼
                   ┌──────────────────┐    terraform apply   ┌──────────────────┐
                   │   ghcr.io        │─────────────────────▶│    Terraform     │
                   │ registry images  │                      │  Docker provider │
                   └──────────────────┘                      └────────┬─────────┘
                                                                      │
                                                       ┌──────────────┴───────────────┐
                                                       ▼                              ▼
                                              ┌──────────────────┐         ┌────────────────────┐
                                              │ sentiment-staging│◀────────│ Prometheus + Grafana│
                                              │   (conteneur)    │ scrape  │    Monitoring       │
                                              └──────────────────┘         └────────────────────┘
```

Tous les services partagent le réseau Docker `cicd-network`.

## Stack technique

| Domaine            | Outils                                                    |
|--------------------|-----------------------------------------------------------|
| Application        | FastAPI, Uvicorn, Pydantic                                |
| Tests              | pytest, pytest-cov (couverture ~91 %)                     |
| Conteneurisation   | Docker, Docker Compose                                     |
| Intégration continue | Jenkins (Pipeline as Code)                              |
| Qualité du code    | SonarQube, flake8                                         |
| Sécurité           | Trivy (scan de vulnérabilités d'images)                   |
| Registry           | GitHub Container Registry (ghcr.io)                       |
| Infrastructure     | Terraform (provider `kreuzwerker/docker`)                 |
| Observabilité      | Prometheus, Grafana, prometheus-fastapi-instrumentator   |

## Structure du dépôt

```
sentiment-ai/
├── src/                      # Code de l'application FastAPI
│   ├── main.py               # Endpoints + instrumentation Prometheus
│   ├── model.py              # Logique du modèle de sentiment
│   └── schemas.py            # Schémas Pydantic (requête / réponse)
├── tests/                    # Tests pytest
├── infra/                    # Infrastructure as Code (Terraform)
│   ├── main.tf               # Provider Docker + ressources (réseau, image, conteneur)
│   ├── variables.tf          # Variables paramétrables
│   └── outputs.tf            # Sorties (URL, ID conteneur, réseau)
├── monitoring/               # Stack d'observabilité
│   ├── prometheus.yml        # Configuration de scrape
│   ├── alerts.yml            # Règles d'alerte
│   └── docker-compose.yml    # Prometheus + Grafana
├── Dockerfile                # Image de l'application
├── docker-compose.yml        # Déploiement local de l'app
├── Jenkinsfile               # Définition du pipeline CI/CD
├── Makefile                  # Cibles build / run / test / clean
└── requirements.txt          # Dépendances Python
```

## Démarrage rapide

### Prérequis

- Docker Desktop
- Python 3.11+ (pour le développement local)
- Terraform 1.7+

### Lancer l'application en local

```bash
python -m venv venv
source venv/bin/activate        # Windows : .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn src.main:app --port 8000
```

L'API est disponible sur `http://localhost:8000`.

### Déployer l'environnement staging avec Terraform

```bash
docker build -t sentiment-ai:latest .
cd infra
terraform init
terraform apply
```

Le conteneur `sentiment-staging` est exposé sur `http://localhost:8001`.

### Lancer la stack de monitoring

```bash
cd monitoring
docker compose up -d
```

- Prometheus : `http://localhost:9090`
- Grafana : `http://localhost:3000` (admin / admin)

## API

| Méthode | Endpoint    | Description                                          |
|---------|-------------|------------------------------------------------------|
| `GET`   | `/health`   | Healthcheck, renvoie `{"status": "ok"}`             |
| `POST`  | `/predict`  | Analyse de sentiment d'un texte                      |
| `GET`   | `/metrics`  | Métriques au format Prometheus                       |

Exemple :

```bash
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"text": "Ce produit est excellent !"}'
# → {"label": "POSITIVE", "score": 0.7, "text": "Ce produit est excellent !"}
```

## Observabilité

L'application est instrumentée avec des métriques HTTP automatiques et trois métriques métier :

| Métrique                                  | Type      | Description                                  |
|-------------------------------------------|-----------|----------------------------------------------|
| `sentiment_predictions_total`             | Counter   | Nombre total de prédictions (par label/statut) |
| `sentiment_confidence_score`              | Gauge     | Score de confiance de la dernière prédiction |
| `sentiment_prediction_duration_seconds`   | Histogram | Durée des prédictions                        |

Le dashboard Grafana présente quatre panels : requêtes/s, latence p99, taux d'erreurs et score de
confiance moyen. Trois règles d'alerte sont définies (latence p99 élevée, taux d'erreurs 5xx,
confiance faible).

## Infrastructure as Code

L'environnement staging est entièrement décrit en Terraform via le provider Docker. Le workflow
`init → plan → apply` est idempotent : un second `apply` sans modification renvoie `No changes`.
Les ressources gérées sont le réseau `cicd-network`, l'image `sentiment-ai` et le conteneur staging.

## Pipeline CI/CD

Le pipeline Jenkins (Pipeline as Code, versionné dans le `Jenkinsfile`) enchaîne les étapes
suivantes : `Checkout → Lint → IaC Validate → Build & Test → SonarQube Analysis → Quality Gate →
Push → IaC Apply → Deploy Staging → Smoke Test`. Le déclenchement est automatique via Poll SCM, et
chaque image est taguée avec le SHA Git du commit pour une traçabilité complète.

## Progression des TP

| TP  | Sujet                          | Statut      |
|-----|--------------------------------|-------------|
| TP1 | Git & Docker                   | ✅ Terminé   |
| TP2 | Jenkins Pipeline               | ✅ Terminé   |
| TP3 | Qualité & Sécurité (Sonar/Trivy) | 🚧 Partie Trivy faite |
| TP4 | Terraform & IaC                | ✅ Parties 1-3 |
| TP5 | Monitoring & Observabilité     | ✅ Parties 1-3 |

## Auteur

**Tchimkio Kouamo Randy Neil** — Mastère 1 DWM, ESTIAM Paris
Module DevOps — Project Management & Ability — 2026
