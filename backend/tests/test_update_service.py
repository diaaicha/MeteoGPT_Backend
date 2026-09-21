from types import SimpleNamespace

from backend.app.services import update_service


def make_settings(
    *,
    enable_admin_update=True,
):
    return SimpleNamespace(
        enable_admin_update=enable_admin_update,
        anacim_api_url="http://test-anacim.local/api",
        qdrant_collection="test_collection",
    )


def test_update_service_disabled(
    monkeypatch,
):
    monkeypatch.setattr(
        update_service,
        "get_settings",
        lambda: make_settings(
            enable_admin_update=False,
        ),
    )

    result = update_service.run_anacim_update(
        dry_run=True,
    )

    assert result["status"] == "disabled"
    assert result["dry_run"] is True
    assert result["update"] is None
    assert result["bm25_refresh"] is None
    assert (
        result["error"]
        == "admin_update_disabled"
    )


def test_update_service_dry_run_does_not_refresh_bm25(
    monkeypatch,
):
    fake_client = object()

    monkeypatch.setattr(
        update_service,
        "get_settings",
        lambda: make_settings(),
    )

    monkeypatch.setattr(
        update_service.retriever,
        "obtenir_client_qdrant_actif",
        lambda: fake_client,
    )

    monkeypatch.setattr(
        update_service,
        "update_api_pipeline",
        lambda **kwargs: {
            "status": "dry_run",
            "counts": {
                "bulletins_api": 4,
                "bulletins_a_traiter": 4,
            },
        },
    )

    def fail_if_refresh_called():
        raise AssertionError(
            "BM25 ne doit pas être rafraîchi "
            "pendant un dry-run."
        )

    monkeypatch.setattr(
        update_service.retriever,
        "refresh_bm25_index",
        fail_if_refresh_called,
    )

    result = update_service.run_anacim_update(
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert result["bm25_refresh"] is None
    assert result["error"] is None


def test_update_service_success_refreshes_bm25(
    monkeypatch,
):
    fake_client = object()

    captured = {}

    monkeypatch.setattr(
        update_service,
        "get_settings",
        lambda: make_settings(),
    )

    monkeypatch.setattr(
        update_service.retriever,
        "obtenir_client_qdrant_actif",
        lambda: fake_client,
    )

    def fake_update_api_pipeline(
        **kwargs,
    ):
        captured.update(kwargs)

        return {
            "status": "success",
            "counts": {
                "bulletins_api": 4,
                "bulletins_a_traiter": 4,
                "new_chunks": 20,
            },
        }

    monkeypatch.setattr(
        update_service,
        "update_api_pipeline",
        fake_update_api_pipeline,
    )

    monkeypatch.setattr(
        update_service.retriever,
        "refresh_bm25_index",
        lambda: {
            "chunks": 365,
            "localites": 19,
        },
    )

    result = update_service.run_anacim_update(
        dry_run=False,
    )

    assert result["status"] == "success"
    assert result["dry_run"] is False
    assert result["error"] is None

    assert result["bm25_refresh"] == {
        "chunks": 365,
        "localites": 19,
    }

    assert captured["qdrant_client"] is fake_client
    assert captured["dry_run"] is False
    assert (
        captured["collection_name"]
        == "test_collection"
    )
    assert (
        captured["api_url"]
        == "http://test-anacim.local/api"
    )