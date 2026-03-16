"""
Unit tests for dm_chain_utils.dm_schema_reg_client.get_schema.
HTTP requests and boto3 are mocked — no live services required.
"""
import os
import pytest
import json
from unittest.mock import patch, MagicMock

import dm_chain_utils.dm_schema_reg_client as src_module


SAMPLE_SCHEMA = json.dumps({"type": "record", "name": "Test", "fields": [{"name": "id", "type": "int"}]})


@pytest.fixture(autouse=True)
def reset_app_env(monkeypatch):
    """Reset APP_ENV module-level var before each test."""
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setattr(src_module, "APP_ENV", "dev")
    yield
    monkeypatch.setattr(src_module, "APP_ENV", "dev")


class TestDevSchemaReg:

    def test_get_schema_dev_auto_registers_and_returns(self, tmp_path, monkeypatch):
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(SAMPLE_SCHEMA)

        with patch("dm_chain_utils.dm_schema_reg_client.requests") as mock_req:
            # check: schema not found → register it
            mock_check = MagicMock()
            mock_check.status_code = 404
            mock_reg = MagicMock()
            mock_reg.json.return_value = {"id": 1}
            mock_compat = MagicMock()
            mock_fetch = MagicMock()
            mock_fetch.json.return_value = {"schema": SAMPLE_SCHEMA}

            mock_req.get.side_effect = [mock_check, mock_fetch]
            mock_req.post.return_value = mock_reg
            mock_req.put.return_value = mock_compat

            result = src_module.get_schema("test-schema", str(schema_file))

        assert result == SAMPLE_SCHEMA

    def test_get_schema_dev_skips_register_if_exists(self, tmp_path, monkeypatch):
        schema_file = tmp_path / "schema.json"
        schema_file.write_text(SAMPLE_SCHEMA)

        with patch("dm_chain_utils.dm_schema_reg_client.requests") as mock_req:
            mock_check = MagicMock()
            mock_check.status_code = 200
            mock_compat = MagicMock()
            mock_fetch = MagicMock()
            mock_fetch.json.return_value = {"schema": SAMPLE_SCHEMA}

            mock_req.get.side_effect = [mock_check, mock_fetch]
            mock_req.put.return_value = mock_compat

            result = src_module.get_schema("test-schema", str(schema_file))

        assert result == SAMPLE_SCHEMA
        mock_req.post.assert_not_called()

    def test_get_schema_dev_raises_without_schema_path(self):
        with pytest.raises(ValueError, match="schema_path is required"):
            src_module.get_schema("test-schema", schema_path=None)


class TestProdSchemaReg:

    def test_get_schema_prod_uses_glue(self, monkeypatch):
        monkeypatch.setattr(src_module, "APP_ENV", "prod")

        with patch("dm_chain_utils.dm_schema_reg_client._glue_get_schema") as mock_glue:
            mock_glue.return_value = SAMPLE_SCHEMA
            result = src_module.get_schema("test-schema")

        mock_glue.assert_called_once_with("test-schema")
        assert result == SAMPLE_SCHEMA

    def test_glue_get_schema_calls_boto3(self, monkeypatch):
        monkeypatch.setenv("GLUE_REGISTRY_NAME", "MyRegistry")
        mock_client = MagicMock()
        mock_client.get_schema_version.return_value = {"SchemaDefinition": SAMPLE_SCHEMA}

        with patch("boto3.client", return_value=mock_client):
            result = src_module._glue_get_schema("test-schema")

        assert result == SAMPLE_SCHEMA
        mock_client.get_schema_version.assert_called_once()
