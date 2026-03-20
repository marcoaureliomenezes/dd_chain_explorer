"""
Unit tests for dm_chain_utils.dm_kinesis.KinesisHandler.
All boto3 calls are mocked — no AWS credentials required.
"""
import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from dm_chain_utils.dm_kinesis import KinesisHandler


@pytest.fixture
def logger():
    return logging.getLogger("test_kinesis")


@pytest.fixture
def handler(logger):
    with patch("dm_chain_utils.dm_kinesis.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        h = KinesisHandler(logger, region="us-east-1")
        yield h


# ------------------------------------------------------------------
# put_record
# ------------------------------------------------------------------


def test_put_record_appends_newline(handler):
    handler.client.put_record.return_value = {
        "ShardId": "shardId-000000000000",
        "SequenceNumber": "123",
    }
    resp = handler.put_record("my-stream", '{"key":"value"}', "pk1")

    call_kwargs = handler.client.put_record.call_args.kwargs
    assert call_kwargs["Data"] == b'{"key":"value"}\n'
    assert call_kwargs["StreamName"] == "my-stream"
    assert call_kwargs["PartitionKey"] == "pk1"
    assert resp["ShardId"] == "shardId-000000000000"


def test_put_record_does_not_double_newline(handler):
    handler.client.put_record.return_value = {
        "ShardId": "shardId-000000000000",
        "SequenceNumber": "456",
    }
    handler.put_record("my-stream", '{"a":1}\n', "pk2")

    call_kwargs = handler.client.put_record.call_args.kwargs
    assert call_kwargs["Data"] == b'{"a":1}\n'


def test_put_record_raises_on_client_error(handler):
    handler.client.put_record.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "Stream not found"}},
        "PutRecord",
    )
    with pytest.raises(ClientError):
        handler.put_record("bad-stream", "{}", "pk")


# ------------------------------------------------------------------
# put_records
# ------------------------------------------------------------------


def test_put_records_batch(handler):
    handler.client.put_records.return_value = {
        "FailedRecordCount": 0,
        "Records": [{"ShardId": "s0", "SequenceNumber": "1"}],
    }
    records = [{"Data": '{"a":1}', "PartitionKey": "k1"}]
    resp = handler.put_records("my-stream", records)

    assert resp["FailedRecordCount"] == 0
    handler.client.put_records.assert_called_once()


def test_put_records_logs_warning_on_failures(handler):
    handler.client.put_records.return_value = {
        "FailedRecordCount": 1,
        "Records": [],
    }
    handler.logger = MagicMock()
    handler.put_records("my-stream", [{"Data": "{}", "PartitionKey": "k"}])
    handler.logger.warning.assert_called_once()


# ------------------------------------------------------------------
# get_shard_iterator
# ------------------------------------------------------------------


def test_get_shard_iterator(handler):
    handler.client.get_shard_iterator.return_value = {"ShardIterator": "AAAA"}
    it = handler.get_shard_iterator("stream", "shardId-000000000000", "LATEST")
    assert it == "AAAA"


def test_get_shard_iterator_with_sequence_number(handler):
    handler.client.get_shard_iterator.return_value = {"ShardIterator": "BBBB"}
    it = handler.get_shard_iterator(
        "stream", "shardId-000000000000", "AFTER_SEQUENCE_NUMBER",
        starting_sequence_number="seq-123",
    )
    call_kwargs = handler.client.get_shard_iterator.call_args.kwargs
    assert call_kwargs["StartingSequenceNumber"] == "seq-123"
    assert it == "BBBB"


# ------------------------------------------------------------------
# get_records
# ------------------------------------------------------------------


def test_get_records(handler):
    handler.client.get_records.return_value = {
        "Records": [{"Data": b'{"x":1}', "SequenceNumber": "1"}],
        "NextShardIterator": "NEXT",
    }
    resp = handler.get_records("iterator-abc", limit=50)
    assert len(resp["Records"]) == 1
    assert resp["NextShardIterator"] == "NEXT"
