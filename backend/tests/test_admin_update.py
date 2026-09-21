from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.api.routes import (
    admin_update,
)


client = TestClient(app)


def test_admin_update_dry_run_success(
    monkeypatch,
):
    monkeypatch.setattr(
        admin_update.update_service,
        "run_anacim_update",
        lambda dry_run: {
            "status": "dry_run",
            "dry_run": dry_run,
            "update": {
                "status": "dry_run",
                "counts": {
                    "bulletins_api": 4,
                    "bulletins_a_traiter": 4,
                },
            },
            "bm25_refresh": None,
            "error": None,
        },
    )

    response = client.post(
        "/api/v1/admin/update",
        json={
            "dry_run": True,
        },
    )

    assert response.status_code == 200

    body = response.json()

    assert body["status"] == "dry_run"
    assert body["dry_run"] is True
    assert body["bm25_refresh"] is None
    assert body["error"] is None


def test_admin_update_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        admin_update.update_service,
        "run_anacim_update",
        lambda dry_run: {
            "status": "disabled",
            "dry_run": dry_run,
            "update": None,
            "bm25_refresh": None,
            "error": "admin_update_disabled",
        },
    )

    response = client.post(
        "/api/v1/admin/update",
        json={
            "dry_run": True,
        },
    )

    assert response.status_code == 503

    assert (
        response.json()["detail"]
        == "L'actualisation ANACIM est désactivée."
    )


def test_admin_update_internal_error(
    monkeypatch,
):
    monkeypatch.setattr(
        admin_update.update_service,
        "run_anacim_update",
        lambda dry_run: {
            "status": "error",
            "dry_run": dry_run,
            "update": None,
            "bm25_refresh": None,
            "error": "test_error",
        },
    )

    response = client.post(
        "/api/v1/admin/update",
        json={
            "dry_run": False,
        },
    )

    assert response.status_code == 500

    assert response.json()["detail"] == (
        "Une erreur interne est survenue pendant "
        "l'actualisation du corpus ANACIM."
    )