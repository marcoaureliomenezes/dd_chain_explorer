"""
Unit tests for dm_chain_utils.dm_kafka_admin.KafkaAdminClient.
All external dependencies (AdminClient) are mocked.
"""
import pytest
from unittest.mock import MagicMock, patch
import logging

from dm_chain_utils.dm_kafka_admin import KafkaAdminClient


@pytest.fixture
def mock_admin_client():
    with patch("dm_chain_utils.dm_kafka_admin.AdminClient") as MockAdmin:
        yield MockAdmin


@pytest.fixture
def kafka_admin(mock_admin_client):
    logger = logging.getLogger("test")
    client = KafkaAdminClient(logger=logger, cluster_conf={"bootstrap.servers": "localhost:9092"})
    return client


def test_list_topics_excludes_internal(kafka_admin, mock_admin_client):
    mock_meta = MagicMock()
    mock_meta.topics.keys.return_value = ["mainnet.1.blocks", "_schemas", "mainnet.2.txs"]
    kafka_admin.kafka_admin.list_topics.return_value = mock_meta

    result = kafka_admin.list_topics()
    assert "_schemas" not in result
    assert "mainnet.1.blocks" in result
    assert "mainnet.2.txs" in result


def test_check_if_topic_exists_true(kafka_admin):
    kafka_admin.list_topics = MagicMock(return_value=["mainnet.1.blocks"])
    assert kafka_admin.check_if_topic_exists("mainnet.1.blocks") is True


def test_check_if_topic_exists_false(kafka_admin):
    kafka_admin.list_topics = MagicMock(return_value=["mainnet.1.blocks"])
    assert kafka_admin.check_if_topic_exists("mainnet.99.unknown") is False


def test_create_topic_skips_if_exists(kafka_admin, caplog):
    kafka_admin.check_if_topic_exists = MagicMock(return_value=True)
    kafka_admin.kafka_admin.create_topics = MagicMock()

    with caplog.at_level(logging.INFO):
        kafka_admin.create_topic("existing-topic", 1, 1)

    kafka_admin.kafka_admin.create_topics.assert_not_called()


def test_create_topic_creates_if_not_exists(kafka_admin):
    kafka_admin.check_if_topic_exists = MagicMock(return_value=False)
    kafka_admin.kafka_admin.create_topics = MagicMock()

    kafka_admin.create_topic("new-topic", 3, 1)

    kafka_admin.kafka_admin.create_topics.assert_called_once()


def test_create_topic_with_overwrite_deletes_first(kafka_admin):
    kafka_admin.delete_topic = MagicMock()
    kafka_admin.check_if_topic_exists = MagicMock(return_value=False)
    kafka_admin.kafka_admin.create_topics = MagicMock()

    kafka_admin.create_topic("existing-topic", 3, 1, overwrite=True)

    kafka_admin.delete_topic.assert_called_once_with("existing-topic")
