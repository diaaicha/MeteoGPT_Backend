from backend.app.core.config import (
    PROJECT_ROOT,
    Settings,
)


def test_default_environment():
    settings = Settings()

    assert settings.app_env == "development"


def test_api_prefix():
    settings = Settings()

    assert settings.api_v1_prefix == "/api/v1"


def test_project_root_exists():
    assert PROJECT_ROOT.exists()


def test_absolute_data_dir():
    settings = Settings()

    assert settings.absolute_data_dir.is_absolute()


def test_absolute_qdrant_path():
    settings = Settings()

    assert settings.absolute_qdrant_path.is_absolute()


def test_whatsapp_disabled_by_default():
    settings = Settings()

    assert settings.enable_whatsapp is False