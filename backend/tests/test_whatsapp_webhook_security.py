
# -*- coding: utf-8 -*-

"""
XamMeteo — Tests de sécurité du webhook WhatsApp.

Vérifications :
- signature HMAC-SHA256 valide ;
- signature absente ;
- signature incorrecte ;
- modification du contenu signé ;
- App Secret absent ;
- vérification GET du webhook préservée.

Aucun message réel n'est envoyé à Meta.
"""

import hashlib
import hmac


from types import SimpleNamespace

import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.routes import (
    whatsapp as whatsapp_routes,
)


# ============================================================
# 1. DONNÉES DE TEST
# ============================================================

APP_SECRET = "secret-de-test-non-reel"

PAYLOAD = (
    b'{"object":"whatsapp_business_account","entry":[]}'
)


# ============================================================
# 2. ENVIRONNEMENT DE TEST
# ============================================================

@pytest.fixture
def environnement(monkeypatch):

    """
    Crée une application FastAPI isolée.

    La configuration Meta est simulée.
    Aucune clé réelle n'est utilisée.
    """

    settings = SimpleNamespace(
        enable_whatsapp=True,
        whatsapp_app_secret=APP_SECRET,
        whatsapp_verify_token="verify-test",
    )

    monkeypatch.setattr(
        whatsapp_routes,
        "get_settings",
        lambda: settings,
    )

    app = FastAPI()

    app.include_router(
        whatsapp_routes.router
    )

    with TestClient(app) as client:
        yield client, settings


# ============================================================
# 3. GÉNÉRATION DE SIGNATURE HMAC-SHA256
# ============================================================

def signer(payload=PAYLOAD):

    """
    Génère une signature conforme au format Meta.

    La signature est calculée sur les octets
    exacts du corps de la requête.
    """

    empreinte = hmac.new(
        APP_SECRET.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    return "sha256=" + empreinte


# ============================================================
# 4. ENVOI D'UNE REQUÊTE HTTP SIMULÉE
# ============================================================

def envoyer(
    client,
    payload=PAYLOAD,
    signature=None,
):

    """
    Envoie une requête POST au webhook.

    La signature est ajoutée uniquement
    lorsqu'elle est fournie.

    La requête est exécutée dans tous les cas,
    y compris lorsqu'aucune signature n'est présente.
    """

    headers = {
        "Content-Type": "application/json",
    }

    if signature is not None:

        headers["X-Hub-Signature-256"] = signature

    # IMPORTANT :
    # L'appel POST est en dehors du bloc if.

    response = client.post(
        "/whatsapp/webhook",
        content=payload,
        headers=headers,
    )

    # Diagnostic temporaire.

    print(
        "\nSTATUT HTTP :",
        response.status_code,
    )

    print(
        "DETAIL :",
        response.text,
    )

    return response


# ============================================================
# 5. SIGNATURE VALIDE
# ============================================================

def test_signature_valide_acceptee(
    environnement,
):

    """
    Une requête correctement signée
    doit être acceptée.
    """

    client, _ = environnement

    response = envoyer(
        client,
        signature=signer(),
    )

    assert response.status_code == 200

    assert (
        response.json()["status"]
        == "received"
    )


# ============================================================
# 6. SIGNATURE ABSENTE
# ============================================================

def test_signature_absente_rejetee(
    environnement,
):

    """
    Une requête sans signature
    doit être rejetée.
    """

    client, _ = environnement

    response = envoyer(
        client,
    )

    assert response.status_code == 403


# ============================================================
# 7. SIGNATURE INCORRECTE
# ============================================================

def test_signature_incorrecte_rejetee(
    environnement,
):

    """
    Une signature incorrecte
    doit être rejetée.
    """

    client, _ = environnement

    response = envoyer(
        client,
        signature=(
            "sha256=" + "0" * 64
        ),
    )

    assert response.status_code == 403


# ============================================================
# 8. CONTENU MODIFIÉ APRÈS SIGNATURE
# ============================================================

def test_payload_modifie_rejete(
    environnement,
):

    """
    Une modification du corps HTTP
    doit invalider sa signature.
    """

    client, _ = environnement

    # Signature du corps initial.

    signature = signer(
        PAYLOAD
    )

    # Ajout d'un espace après signature.

    payload_modifie = (
        PAYLOAD + b" "
    )

    response = envoyer(
        client,
        payload=payload_modifie,
        signature=signature,
    )

    assert response.status_code == 403


# ============================================================
# 9. APP SECRET ABSENT
# ============================================================

def test_cle_absente_refuse_webhook(
    environnement,
):

    """
    Si l'App Secret n'est pas configuré,
    le webhook doit refuser les POST.
    """

    client, settings = environnement

    settings.whatsapp_app_secret = None

    response = envoyer(
        client,
        signature=signer(),
    )

    assert response.status_code == 503


# ============================================================
# 10. VÉRIFICATION GET PRÉSERVÉE
# ============================================================

def test_verification_get_preservee(
    environnement,
):

    """
    La vérification GET utilisée par Meta
    doit continuer à fonctionner.
    """

    client, _ = environnement

    response = client.get(
        "/whatsapp/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-test",
            "hub.challenge": "123456",
        },
    )

    assert response.status_code == 200

    assert response.text == "123456"
