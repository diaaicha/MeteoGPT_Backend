
# -*- coding: utf-8 -*-

"""
Tests HTTP des routes de personnalisation.
"""

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.personalization import (
    router,
    get_personalization_service,
)

from backend.app.services.personalization_service import (
    PersonalizationService,
)

from backend.app.services.user_profile_service import (
    UserProfileStore,
    STATUS_NEW,
    STATUS_ACCEPTED,
)


# ============================================================
# 1. FIXTURES
# ============================================================

@pytest.fixture
def store(tmp_path):

    return UserProfileStore(
        database_path=(
            tmp_path
            / "test_personalization_routes.sqlite3"
        )
    )


@pytest.fixture
def service(store):

    return PersonalizationService(
        profile_store=store
    )


@pytest.fixture
def client(service):

    app = FastAPI()

    app.include_router(
        router
    )

    app.dependency_overrides[
        get_personalization_service
    ] = lambda: service

    with TestClient(app) as test_client:

        yield test_client


# ============================================================
# 2. OUVERTURE
# ============================================================

def test_ouvrir_formulaire_creation(
    client,
    service,
):

    token = service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/ouvrir",

        json={
            "token": token,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True

    formulaire = data["formulaire"]

    assert formulaire["mode"] == "creation"

    assert formulaire["first_name"] == ""

    assert formulaire["last_name"] == ""

    assert "user_id" not in formulaire


def test_ouvrir_formulaire_modification(
    client,
    service,
    store,
):

    store.enregistrer_identite(
        "user-001",
        "Mariam",
        "Ndiaye",
    )

    token = service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/ouvrir",

        json={
            "token": token,
        },
    )

    assert response.status_code == 200

    formulaire = response.json()[
        "formulaire"
    ]

    assert (
        formulaire["mode"]
        == "modification"
    )

    assert formulaire["first_name"] == "Mariam"

    assert formulaire["last_name"] == "Ndiaye"

    assert formulaire["button_label"] == (
        "Modifier mes informations personnelles"
    )


# ============================================================
# 3. ENREGISTREMENT
# ============================================================

def test_validation_creation(
    client,
    service,
    store,
):

    token = service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/valider",

        json={
            "token": token,
            "first_name": "Mariam",
            "last_name": "Ndiaye",
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["success"] is True

    assert data["mode"] == "creation"

    assert data["first_name"] == "Mariam"

    assert "user_id" not in data

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_ACCEPTED
    )

    assert profil["first_name"] == "Mariam"

    assert profil["last_name"] == "Ndiaye"


def test_validation_modification(
    client,
    service,
    store,
):

    store.enregistrer_identite(
        "user-001",
        "Mariam",
        "Ndiaye",
    )

    token = service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/valider",

        json={
            "token": token,
            "first_name": "Fatou",
            "last_name": "Fall",
        },
    )

    assert response.status_code == 200

    assert (
        response.json()["mode"]
        == "modification"
    )

    profil = store.charger_profil(
        "user-001"
    )

    assert profil["first_name"] == "Fatou"

    assert profil["last_name"] == "Fall"


# ============================================================
# 4. TOKEN INVALIDÉ
# ============================================================

def test_double_validation_interdite(
    client,
    service,
    store,
):

    token = service.generer_token(
        "user-001"
    )

    donnees = {
        "token": token,
        "first_name": "Mariam",
        "last_name": "Ndiaye",
    }

    response = client.post(
        "/personnalisation/valider",
        json=donnees,
    )

    assert response.status_code == 200

    donnees["first_name"] = "Fatou"

    response = client.post(
        "/personnalisation/valider",
        json=donnees,
    )

    assert response.status_code == 410

    assert response.json()["success"] is False

    profil = store.charger_profil(
        "user-001"
    )

    assert profil["first_name"] == "Mariam"


def test_ancien_token_invalide(
    client,
    service,
):

    ancien = service.generer_token(
        "user-001"
    )

    service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/ouvrir",

        json={
            "token": ancien,
        },
    )

    assert response.status_code == 410


@pytest.mark.parametrize(
    "token",
    [
        "",
        "invalide",
        None,
        "A" * 43,
    ],
)
def test_token_invalide(
    client,
    token,
):

    response = client.post(

        "/personnalisation/ouvrir",

        json={
            "token": token,
        },
    )

    assert response.status_code == 410

    assert response.json()["success"] is False


# ============================================================
# 5. VALIDATION DES CHAMPS
# ============================================================

@pytest.mark.parametrize(
    "first_name,last_name",
    [
        ("", "Ndiaye"),
        ("Mariam", ""),
        ("123", "Ndiaye"),
        ("Mariam", "@@@"),
        (None, "Ndiaye"),
    ],
)
def test_identite_invalide(
    client,
    service,
    store,
    first_name,
    last_name,
):

    token = service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/valider",

        json={
            "token": token,
            "first_name": first_name,
            "last_name": last_name,
        },
    )

    assert response.status_code == 422

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_NEW
    )

    # Le token reste disponible pour corriger
    # les informations saisies.

    response = client.post(

        "/personnalisation/ouvrir",

        json={
            "token": token,
        },
    )

    assert response.status_code == 200


# ============================================================
# 6. ANNULATION
# ============================================================

def test_annulation_creation(
    client,
    service,
    store,
):

    token = service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/annuler",

        json={
            "token": token,
        },
    )

    assert response.status_code == 200

    assert response.json()["success"] is True

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_NEW
    )

    response = client.post(

        "/personnalisation/ouvrir",

        json={
            "token": token,
        },
    )

    assert response.status_code == 410


def test_annulation_modification(
    client,
    service,
    store,
):

    ancien_profil = store.enregistrer_identite(
        "user-001",
        "Mariam",
        "Ndiaye",
    )

    token = service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/annuler",

        json={
            "token": token,
        },
    )

    assert response.status_code == 200

    assert (
        store.charger_profil("user-001")
        == ancien_profil
    )


# ============================================================
# 7. ISOLATION DES UTILISATEURS
# ============================================================

def test_identifiant_externe_refuse(
    client,
    service,
    store,
):

    token = service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/valider",

        json={
            "token": token,
            "first_name": "Mariam",
            "last_name": "Ndiaye",

            # Tentative de modifier un autre profil.
            "user_id": "user-002",
        },
    )

    assert response.status_code == 422

    assert (
        store.charger_profil(
            "user-002"
        )["personalization_status"]
        == STATUS_NEW
    )

    assert (
        store.charger_profil(
            "user-001"
        )["personalization_status"]
        == STATUS_NEW
    )


# ============================================================
# 8. SÉCURITÉ HTTP
# ============================================================

def test_entetes_securite(
    client,
    service,
):

    token = service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/ouvrir",

        json={
            "token": token,
        },
    )

    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )

    assert (
        response.headers["Referrer-Policy"]
        == "no-referrer"
    )

    assert (
        response.headers["X-Frame-Options"]
        == "DENY"
    )

    assert token not in response.text


def test_format_non_json_refuse(
    client,
):

    response = client.post(

        "/personnalisation/ouvrir",

        data={
            "token": "invalide"
        },
    )

    assert response.status_code == 400


def test_corps_json_invalide(
    client,
):

    response = client.post(

        "/personnalisation/ouvrir",

        content="{",

        headers={
            "Content-Type": "application/json"
        },
    )

    assert response.status_code == 400


def test_requete_trop_volumineuse(
    client,
):

    response = client.post(

        "/personnalisation/ouvrir",

        json={
            "token": "A" * 5000,
        },
    )

    assert response.status_code == 400


def test_erreur_ne_divulgue_pas_token(
    client,
):

    token = "A" * 43

    response = client.post(

        "/personnalisation/ouvrir",

        json={
            "token": token,
        },
    )

    assert response.status_code == 410

    assert token not in response.text

    assert (
        response.headers["Cache-Control"]
        == "no-store"
    )
