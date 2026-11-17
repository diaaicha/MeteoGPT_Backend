
# -*- coding: utf-8 -*-

"""
Tests du service de personnalisation par formulaire web.
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes.personalization import (
    router as personalization_router,
    get_personalization_service,
)


import sqlite3

from contextlib import closing

import pytest

from backend.app.services.user_profile_service import (
    UserProfileStore,
    STATUS_NEW,
    STATUS_ACCEPTED,
    STATUS_DECLINED,
)


from unittest.mock import Mock

from backend.app.services import (
    whatsapp_service as ws,
)

from backend.app.services.personalization_service import (
    PersonalizationService,
    PersonalizationTokenError,
)


# ============================================================
# 1. FIXTURES
# ============================================================

@pytest.fixture
def store(tmp_path):

    return UserProfileStore(

        database_path=(
            tmp_path
            / "test_personalization.sqlite3"
        )
    )


@pytest.fixture
def service(store):

    return PersonalizationService(
        profile_store=store
    )



@pytest.fixture(autouse=True)
def whatsapp_mock(monkeypatch):

    mock = Mock(

        return_value={

            "messages": [

                {
                    "id": "wamid.TEST_CONFIRMATION"
                }
            ]
        }
    )

    monkeypatch.setattr(

        ws,

        "send_whatsapp_text_message",

        mock,
    )

    return mock


@pytest.fixture
def client(service):
    """
    Client HTTP isolé pour les tests de notification.

    Réutilise la base SQLite temporaire du test.
    """

    app = FastAPI()

    app.include_router(
        personalization_router
    )

    app.dependency_overrides[
        get_personalization_service
    ] = lambda: service

    with TestClient(app) as test_client:
        yield test_client


# ============================================================
# 2. GÉNÉRATION ET STOCKAGE
# ============================================================

def test_generation_token(service):

    token = service.generer_token(
        "user-001"
    )

    assert isinstance(token, str)

    assert len(token) == 43

    formulaire = service.charger_formulaire(
        token
    )

    assert formulaire["mode"] == "creation"


def test_token_non_stocke_en_clair(
    service,
    store
):

    token = service.generer_token(
        "user-001"
    )

    with closing(
        store._connect()
    ) as connexion:

        ligne = connexion.execute(
            """
            SELECT token_hash

            FROM personalization_tokens

            WHERE user_id = ?
            """,

            ("user-001",)

        ).fetchone()

    assert ligne["token_hash"] != token

    assert len(ligne["token_hash"]) == 64


def test_generation_preserve_profil(
    service,
    store
):

    service.generer_token("user-001")

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_NEW
    )


# ============================================================
# 3. CHARGEMENT DU FORMULAIRE
# ============================================================

def test_formulaire_initial_vide(service):

    token = service.generer_token(
        "user-001"
    )

    formulaire = service.charger_formulaire(
        token
    )

    assert formulaire["mode"] == "creation"

    assert formulaire["first_name"] == ""

    assert formulaire["last_name"] == ""

    assert (
        formulaire["button_label"]
        == "Valider mes informations"
    )


def test_formulaire_modification_prefilled(
    service,
    store
):

    store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    token = service.generer_token(
        "user-001"
    )

    formulaire = service.charger_formulaire(
        token
    )

    assert (
        formulaire["mode"]
        == "modification"
    )

    assert formulaire["first_name"] == "Mariam"

    assert formulaire["last_name"] == "Ndiaye"

    assert formulaire["button_label"] == (
        "Modifier mes informations personnelles"
    )


def test_ouverture_repetee_ne_consomme_pas_token(
    service
):

    token = service.generer_token(
        "user-001"
    )

    premier = service.charger_formulaire(
        token
    )

    second = service.charger_formulaire(
        token
    )

    assert premier == second


# ============================================================
# 4. ENREGISTREMENT ET MODIFICATION
# ============================================================

def test_validation_creation(
    service,
    store
):

    token = service.generer_token(
        "user-001"
    )

    resultat = service.valider_formulaire(

        token=token,

        first_name="Mariam",

        last_name="Ndiaye",
    )

    assert resultat["mode"] == "creation"

    profil = store.charger_profil(
        "user-001"
    )

    assert profil["first_name"] == "Mariam"

    assert profil["last_name"] == "Ndiaye"

    assert (
        profil["personalization_status"]
        == STATUS_ACCEPTED
    )

    assert (
        profil["personalization_offer_seen"]
        is True
    )


def test_validation_modification(
    service,
    store
):

    store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    token = service.generer_token(
        "user-001"
    )

    resultat = service.valider_formulaire(

        token=token,

        first_name="Fatou",

        last_name="Fall",
    )

    assert (
        resultat["mode"]
        == "modification"
    )

    profil = store.charger_profil(
        "user-001"
    )

    assert profil["first_name"] == "Fatou"

    assert profil["last_name"] == "Fall"


def test_personnalisation_apres_refus(
    service,
    store
):

    store.enregistrer_refus("user-001")

    token = service.generer_token(
        "user-001"
    )

    formulaire = service.charger_formulaire(
        token
    )

    assert formulaire["mode"] == "creation"

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_DECLINED
    )

    service.valider_formulaire(

        token=token,

        first_name="Aminata",

        last_name="Ba",
    )

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_ACCEPTED
    )


# ============================================================
# 5. TOKEN À USAGE UNIQUE
# ============================================================

def test_token_invalide_apres_validation(
    service
):

    token = service.generer_token(
        "user-001"
    )

    service.valider_formulaire(

        token=token,

        first_name="Mariam",

        last_name="Ndiaye",
    )

    with pytest.raises(
        PersonalizationTokenError
    ):

        service.charger_formulaire(
            token
        )


def test_double_validation_interdite(
    service,
    store
):

    token = service.generer_token(
        "user-001"
    )

    service.valider_formulaire(

        token=token,

        first_name="Mariam",

        last_name="Ndiaye",
    )

    with pytest.raises(
        PersonalizationTokenError
    ):

        service.valider_formulaire(

            token=token,

            first_name="Fatou",

            last_name="Fall",
        )

    profil = store.charger_profil(
        "user-001"
    )

    assert profil["first_name"] == "Mariam"

    assert profil["last_name"] == "Ndiaye"


def test_nouveau_token_invalide_ancien(
    service
):

    ancien = service.generer_token(
        "user-001"
    )

    nouveau = service.generer_token(
        "user-001"
    )

    assert ancien != nouveau

    with pytest.raises(
        PersonalizationTokenError
    ):

        service.charger_formulaire(
            ancien
        )

    assert (

        service.charger_formulaire(
            nouveau
        )["mode"]

        == "creation"
    )


# ============================================================
# 6. EXPIRATION
# ============================================================

def test_token_expire(store):

    horloge = [1000.0]

    service = PersonalizationService(

        profile_store=store,

        ttl_seconds=900,

        clock=lambda: horloge[0],
    )

    token = service.generer_token(
        "user-001"
    )

    horloge[0] = 1900.0

    with pytest.raises(
        PersonalizationTokenError
    ):

        service.charger_formulaire(
            token
        )

    with pytest.raises(
        PersonalizationTokenError
    ):

        service.valider_formulaire(

            token=token,

            first_name="Mariam",

            last_name="Ndiaye",
        )

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_NEW
    )


# ============================================================
# 7. TOKENS INVALIDES
# ============================================================

@pytest.mark.parametrize(
    "token",
    [
        "",
        None,
        123,
        "token-invalide",
        "A" * 43,
    ]
)
def test_token_invalide(
    service,
    token
):

    with pytest.raises(
        PersonalizationTokenError
    ):

        service.charger_formulaire(
            token
        )


# ============================================================
# 8. INFORMATIONS INVALIDES
# ============================================================

@pytest.mark.parametrize(
    "first_name,last_name",
    [
        ("", "Ndiaye"),
        ("Mariam", ""),
        ("12345", "Ndiaye"),
        ("Mariam", "12345"),
        ("Mariam@", "Ndiaye"),
        ("A" * 101, "Ndiaye"),
        ("Mariam", "B" * 101),
    ]
)
def test_identite_invalide_preserve_token(
    service,
    store,
    first_name,
    last_name
):

    token = service.generer_token(
        "user-001"
    )

    with pytest.raises(ValueError):

        service.valider_formulaire(

            token=token,

            first_name=first_name,

            last_name=last_name,
        )

    # Le formulaire reste disponible pour correction.

    formulaire = service.charger_formulaire(
        token
    )

    assert formulaire["mode"] == "creation"

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_NEW
    )


def test_noms_unicode_et_normalisation(
    service,
    store
):

    token = service.generer_token(
        "user-001"
    )

    service.valider_formulaire(

        token=token,

        first_name="  Aïssatou   Mariam  ",

        last_name="  N'Diaye  ",
    )

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["first_name"]
        == "Aïssatou Mariam"
    )

    assert profil["last_name"] == "N'Diaye"


# ============================================================
# 9. ANNULATION
# ============================================================

def test_annulation_creation(
    service,
    store
):

    token = service.generer_token(
        "user-001"
    )

    assert service.annuler_formulaire(
        token
    ) is True

    profil = store.charger_profil(
        "user-001"
    )

    assert (
        profil["personalization_status"]
        == STATUS_NEW
    )

    with pytest.raises(
        PersonalizationTokenError
    ):

        service.charger_formulaire(
            token
        )


def test_annulation_modification_preserve_profil(
    service,
    store
):

    ancien_profil = store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    token = service.generer_token(
        "user-001"
    )

    service.annuler_formulaire(
        token
    )

    assert (

        store.charger_profil(
            "user-001"
        )

        == ancien_profil
    )


def test_annulation_repetee(service):

    token = service.generer_token(
        "user-001"
    )

    assert service.annuler_formulaire(
        token
    ) is True

    assert service.annuler_formulaire(
        token
    ) is False


# ============================================================
# 10. ISOLATION
# ============================================================

def test_isolation_tokens(
    service,
    store
):

    token_1 = service.generer_token(
        "user-001"
    )

    token_2 = service.generer_token(
        "user-002"
    )

    service.valider_formulaire(

        token=token_1,

        first_name="Mariam",

        last_name="Ndiaye",
    )

    profil_2 = store.charger_profil(
        "user-002"
    )

    assert (
        profil_2["personalization_status"]
        == STATUS_NEW
    )

    assert (

        service.charger_formulaire(
            token_2
        )["mode"]

        == "creation"
    )


def test_invalidation_utilisateur(
    service,
    store
):

    token_1 = service.generer_token(
        "user-001"
    )

    token_2 = service.generer_token(
        "user-002"
    )

    assert service.invalider_tokens_utilisateur(
        "user-001"
    ) is True

    with pytest.raises(
        PersonalizationTokenError
    ):

        service.charger_formulaire(
            token_1
        )

    assert (

        service.charger_formulaire(
            token_2
        )["mode"]

        == "creation"
    )


# ============================================================
# 11. PERSISTANCE
# ============================================================

def test_token_persistant_apres_reouverture(
    service,
    store
):

    token = service.generer_token(
        "user-001"
    )

    nouveau_store = UserProfileStore(

        database_path=store.database_path
    )

    nouveau_service = PersonalizationService(

        profile_store=nouveau_store
    )

    formulaire = (
        nouveau_service.charger_formulaire(
            token
        )
    )

    assert formulaire["mode"] == "creation"


# ============================================================
# 12. ANCIENNE COLLECTE WHATSAPP
# ============================================================

def test_validation_supprime_ancien_brouillon(
    service,
    store
):

    store.demarrer_collecte(
        "user-001"
    )

    store.enregistrer_prenom_collecte(

        user_id="user-001",

        first_name="Fatou",
    )

    token = service.generer_token(
        "user-001"
    )

    service.valider_formulaire(

        token=token,

        first_name="Mariam",

        last_name="Ndiaye",
    )

    assert (

        store.charger_collecte(
            "user-001"
        )

        is None
    )


# ============================================================
# 13. TRANSACTION ATOMIQUE
# ============================================================

def test_echec_transaction_preserve_profil_et_token(
    service,
    store
):

    ancien_profil = store.enregistrer_identite(

        user_id="user-001",

        first_name="Mariam",

        last_name="Ndiaye",
    )

    token = service.generer_token(
        "user-001"
    )

    # Provoquer une erreur lors de la consommation du token.

    with closing(
        store._connect()
    ) as connexion:

        with connexion:

            connexion.execute(
                """
                CREATE TRIGGER test_block_token_delete

                BEFORE DELETE

                ON personalization_tokens

                BEGIN

                    SELECT RAISE(

                        ABORT,

                        'Suppression interdite'

                    );

                END
                """
            )

    with pytest.raises(
        sqlite3.IntegrityError
    ):

        service.valider_formulaire(

            token=token,

            first_name="Fatou",

            last_name="Fall",
        )

    # L'identité précédente doit rester intacte.

    assert (

        store.charger_profil(
            "user-001"
        )

        == ancien_profil
    )

    # Le token doit toujours être utilisable.

    formulaire = service.charger_formulaire(
        token
    )

    assert formulaire["first_name"] == "Mariam"

    assert formulaire["last_name"] == "Ndiaye"




# ============================================================
# 9. NOTIFICATIONS WHATSAPP
# ============================================================

def test_notification_creation(
    client,
    service,
    whatsapp_mock,
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

    whatsapp_mock.assert_called_once()

    arguments = whatsapp_mock.call_args.kwargs

    assert arguments["recipient"] == "user-001"

    assert "Mariam Ndiaye" in arguments["text"]

    assert "enregistrées" in arguments["text"]


def test_notification_modification(
    client,
    service,
    store,
    whatsapp_mock,
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

    whatsapp_mock.assert_called_once()

    arguments = whatsapp_mock.call_args.kwargs

    assert arguments["recipient"] == "user-001"

    assert "Fatou Fall" in arguments["text"]

    assert "modifiées" in arguments["text"]


def test_echec_notification_preserve_profil(
    client,
    service,
    store,
    whatsapp_mock,
):

    whatsapp_mock.side_effect = RuntimeError(
        "Erreur WhatsApp simulee"
    )

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

    # La validation reste réussie.

    assert response.status_code == 200

    assert response.json()["success"] is True

    profil = store.charger_profil(
        "user-001"
    )

    assert profil["first_name"] == "Mariam"

    assert profil["last_name"] == "Ndiaye"

    assert (
        profil["personalization_status"]
        == STATUS_ACCEPTED
    )

    # Le token reste consommé.

    response = client.post(

        "/personnalisation/ouvrir",

        json={
            "token": token,
        },
    )

    assert response.status_code == 410

    whatsapp_mock.assert_called_once()


def test_annulation_sans_notification(
    client,
    service,
    whatsapp_mock,
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

    whatsapp_mock.assert_not_called()


def test_double_validation_notification_unique(
    client,
    service,
    whatsapp_mock,
):

    token = service.generer_token(
        "user-001"
    )

    donnees = {

        "token": token,

        "first_name": "Mariam",

        "last_name": "Ndiaye",
    }

    premiere = client.post(

        "/personnalisation/valider",

        json=donnees,
    )

    seconde = client.post(

        "/personnalisation/valider",

        json=donnees,
    )

    assert premiere.status_code == 200

    assert seconde.status_code == 410

    whatsapp_mock.assert_called_once()


def test_identite_invalide_sans_notification(
    client,
    service,
    whatsapp_mock,
):

    token = service.generer_token(
        "user-001"
    )

    response = client.post(

        "/personnalisation/valider",

        json={

            "token": token,

            "first_name": "",

            "last_name": "Ndiaye",
        },
    )

    assert response.status_code == 422

    whatsapp_mock.assert_not_called()
