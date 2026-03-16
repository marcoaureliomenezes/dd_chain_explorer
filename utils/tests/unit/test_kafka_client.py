"""
Unit tests for dm_chain_utils.dm_kafka_client.KafkaHandler.
All Confluent Kafka dependencies are mocked.
"""
import pytest
import logging
from unittest.mock import MagicMock, patch, call

from dm_chain_utils.dm_kafka_client import KafkaHandler, SuccessHandler, ErrorHandler


@pytest.fixture
def handler():
    with patch("dm_chain_utils.dm_kafka_client.SchemaRegistryClient"):
        h = KafkaHandler(logger=logging.getLogger("test"), sc_url="http://localhost:8081")
        return h


def test_kafka_handler_initializes(handler):
    assert handler.sc_client is not None


def test_create_avro_producer_pre_warms_broker(handler):
    mock_producer = MagicMock()
    with patch("dm_chain_utils.dm_kafka_client.SerializingProducer", return_value=mock_producer):
        with patch("dm_chain_utils.dm_kafka_client.AvroSerializer"):
            result = handler.create_avro_producer({"bootstrap.servers": "localhost:9092"}, "{}")
    mock_producer.list_topics.assert_called_once_with(timeout=15)


def test_create_avro_consumer_returns_consumer(handler):
    mock_consumer = MagicMock()
    with patch("dm_chain_utils.dm_kafka_client.DeserializingConsumer", return_value=mock_consumer):
        with patch("dm_chain_utils.dm_kafka_client.AvroDeserializer"):
            result = handler.create_avro_consumer({"group.id": "test"}, "{}")
    assert result is mock_consumer


def test_message_handler_calls_success_on_no_error(handler):
    record = MagicMock()
    record.key.return_value = b"key"
    record.partition.return_value = 0
    record.topic.return_value = "test-topic"

    handler.message_handler(None, record)  # should not raise


def test_message_handler_calls_error_on_error(handler, caplog):
    with caplog.at_level(logging.ERROR):
        handler.message_handler("some error", None)
    assert "some error" in caplog.text


def test_success_handler_logs_info(caplog):
    logger = logging.getLogger("test")
    sh = SuccessHandler(logger)
    record = MagicMock()
    record.key.return_value = b"mykey"
    record.partition.return_value = 2
    record.topic.return_value = "mainnet.1.blocks"

    with caplog.at_level(logging.INFO):
        sh(record)

    assert "mainnet.1.blocks" in caplog.text


def test_error_handler_logs_error(caplog):
    logger = logging.getLogger("test")
    eh = ErrorHandler(logger)
    with caplog.at_level(logging.ERROR):
        eh("broker_connection_error")
    assert "broker_connection_error" in caplog.text
