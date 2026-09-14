import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


class TestProductionConfigurationValidation:
    def test_production_rejects_insecure_default_jwt_secret(self):
        with pytest.raises(ValueError, match="JWT_SECRET_KEY must be set to a strong"):
            Settings(
                app_env="production",
                database_url="postgresql+psycopg2://user:pass@ep-host.neon.tech/neondb?sslmode=require",
                gemini_api_key="AIzaSyDummyKeyForProductionTesting12345678",
                jwt_secret_key="contractiq-dev-insecure-secret-key-change-in-production-32bytes",
            )

    def test_production_rejects_short_jwt_secret(self):
        with pytest.raises(ValueError, match="at least 32 characters"):
            Settings(
                app_env="production",
                database_url="postgresql+psycopg2://user:pass@ep-host.neon.tech/neondb?sslmode=require",
                gemini_api_key="AIzaSyDummyKeyForProductionTesting12345678",
                jwt_secret_key="too-short-secret",
            )

    def test_production_rejects_missing_database_url(self):
        with pytest.raises(ValueError, match="DATABASE_URL must be configured"):
            Settings(
                app_env="production",
                database_url="",
                gemini_api_key="AIzaSyDummyKeyForProductionTesting12345678",
                jwt_secret_key="a-very-strong-production-secret-key-that-is-over-32-chars",
            )

    def test_production_rejects_missing_gemini_api_key(self):
        with pytest.raises(ValueError, match="GEMINI_API_KEY must be configured"):
            Settings(
                app_env="production",
                database_url="postgresql+psycopg2://user:pass@ep-host.neon.tech/neondb?sslmode=require",
                gemini_api_key="",
                jwt_secret_key="a-very-strong-production-secret-key-that-is-over-32-chars",
            )

    def test_production_forces_debug_mode_false(self):
        cfg = Settings(
            app_env="production",
            app_debug=True,  # explicitly attempted True
            database_url="postgresql+psycopg2://user:pass@ep-host.neon.tech/neondb?sslmode=require",
            gemini_api_key="AIzaSyDummyKeyForProductionTesting12345678",
            jwt_secret_key="a-very-strong-production-secret-key-that-is-over-32-chars",
        )
        assert cfg.app_debug is False
        assert cfg.is_production is True

    def test_cors_origins_parsing(self):
        cfg = Settings(
            app_env="development",
            cors_origins="https://app.contractiq.com, https://preview.contractiq.com,  ",
        )
        assert cfg.cors_origins_list == [
            "https://app.contractiq.com",
            "https://preview.contractiq.com",
        ]


class TestProductionAppSecurityAndCORS:
    def test_production_cors_allows_configured_origin(self):
        prod_settings = Settings(
            app_env="production",
            app_debug=False,
            database_url="postgresql+psycopg2://user:pass@ep-host.neon.tech/neondb?sslmode=require",
            gemini_api_key="AIzaSyDummyKeyForProductionTesting12345678",
            jwt_secret_key="a-very-strong-production-secret-key-that-is-over-32-chars",
            cors_origins="https://app.contractiq.com",
        )

        with patch("app.main.settings", prod_settings):
            prod_app = create_app()
            client = TestClient(prod_app)

            # Request with allowed origin
            resp = client.get(
                "/health/liveness",
                headers={"Origin": "https://app.contractiq.com"},
            )
            assert resp.status_code == 200
            assert resp.headers.get("access-control-allow-origin") == "https://app.contractiq.com"

            # Request with unallowed origin
            resp_blocked = client.get(
                "/health/liveness",
                headers={"Origin": "https://malicious-site.com"},
            )
            assert resp_blocked.status_code == 200
            assert "access-control-allow-origin" not in resp_blocked.headers

    def test_production_disables_docs_and_redoc(self):
        prod_settings = Settings(
            app_env="production",
            app_debug=False,
            database_url="postgresql+psycopg2://user:pass@ep-host.neon.tech/neondb?sslmode=require",
            gemini_api_key="AIzaSyDummyKeyForProductionTesting12345678",
            jwt_secret_key="a-very-strong-production-secret-key-that-is-over-32-chars",
        )

        with patch("app.main.settings", prod_settings):
            prod_app = create_app()
            client = TestClient(prod_app)

            # /docs should be 404 in production
            docs_resp = client.get("/docs")
            assert docs_resp.status_code == 404

            # /redoc should be 404 in production
            redoc_resp = client.get("/redoc")
            assert redoc_resp.status_code == 404


class TestDeploymentArtifactsAndStaticRouting:
    def test_redirects_file_exists_and_contains_spa_rewrite(self):
        redirects_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "public", "_redirects"
        )
        assert os.path.isfile(redirects_path)
        with open(redirects_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "/*" in content
        assert "/index.html" in content
        assert "200" in content

    def test_vercel_json_exists_and_contains_rewrites(self):
        vercel_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "vercel.json"
        )
        assert os.path.isfile(vercel_path)
        with open(vercel_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "rewrites" in content
        assert "/index.html" in content

    def test_dockerfile_exists(self):
        dockerfile_path = os.path.join(
            os.path.dirname(__file__), "..", "Dockerfile"
        )
        assert os.path.isfile(dockerfile_path)
        with open(dockerfile_path, "r", encoding="utf-8") as f:
            content = f.read()
        assert "python:3.13-slim" in content
        assert "uvicorn" in content
        assert "EXPOSE 8000" in content
