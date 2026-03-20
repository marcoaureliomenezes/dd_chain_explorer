"""
Unit tests for dm_chain_utils.dm_sqs.SQSHandler.
All boto3 calls are mocked — no AWS credentials required.
"""
import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from dm_chain_utils.dm_sqs import SQSHandler


QUEUE_URL = "https://sqs.sa-east-1.amazonaws.com/123456789012/test-queue"


@pytest.fixture
def logger():
    return logging.getLogger("test_sqs")


@pytest.fixture
def handler(logger):
    with patch("dm_chain_utils.dm_sqs.boto3") as mock_boto3:
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        h = SQSHandler(logger, region="us-east-1")
        yield h


# ------------------------------------------------------------------
# send_message
# ------------------------------------------------------------------


def test_send_message(handler):
    handler.client.send_message.return_value = {
        "MessageId": "msg-001",
        "MD5OfMessageBody": "abc123",
    }
    resp = handler.send_message(QUEUE_URL, '{"block_number": 100}')

    handler.client.send_message.assert_called_once_with(
        QueueUrl=QUEUE_URL,
        MessageBody='{"block_number": 100}',
    )
    assert resp["MessageId"] == "msg-001"


def test_send_message_with_attributes(handler):
    handler.client.send_message.return_value = {"MessageId": "msg-002"}
    attrs = {"source": {"StringValue": "job1", "DataType": "String"}}
    handler.send_message(QUEUE_URL, "{}", message_attributes=attrs)

    call_kwargs = handler.client.send_message.call_args.kwargs
    assert call_kwargs["MessageAttributes"] == attrs


def test_send_message_raises_on_error(handler):
    handler.client.send_message.side_effect = ClientError(
        {"Error": {"Code": "QueueDoesNotExist", "Message": "not found"}},
        "SendMessage",
    )
    with pytest.raises(ClientError):
        handler.send_message(QUEUE_URL, "{}")


# ------------------------------------------------------------------
# send_message_batch
# ------------------------------------------------------------------


def test_send_message_batch_single_chunk(handler):
    handler.client.send_message_batch.return_value = {
        "Successful": [{"Id": "0", "MessageId": "m1"}],
        "Failed": [],
    }
    entries = [{"MessageBody": '{"a":1}'}]
    resp = handler.send_message_batch(QUEUE_URL, entries)
    assert len(resp["Successful"]) == 1
    assert len(resp["Failed"]) == 0


def test_send_message_batch_chunks_over_10(handler):
    handler.client.send_message_batch.return_value = {
        "Successful": [{"Id": str(i)} for i in range(10)],
        "Failed": [],
    }
    entries = [{"MessageBody": f'{{"i":{i}}}'} for i in range(15)]
    handler.send_message_batch(QUEUE_URL, entries)

    # Should be called twice: first 10, then 5
    assert handler.client.send_message_batch.call_count == 2


# ------------------------------------------------------------------
# receive_messages
# ------------------------------------------------------------------


def test_receive_messages(handler):
    handler.client.receive_message.return_value = {
        "Messages": [
            {"MessageId": "m1", "ReceiptHandle": "rh1", "Body": '{"x":1}'},
        ],
    }
    msgs = handler.receive_messages(QUEUE_URL, max_messages=5, wait_time_seconds=10)
    assert len(msgs) == 1
    assert msgs[0]["Body"] == '{"x":1}'


def test_receive_messages_empty(handler):
    handler.client.receive_message.return_value = {}
    msgs = handler.receive_messages(QUEUE_URL)
    assert msgs == []


def test_receive_messages_caps_at_10(handler):
    handler.client.receive_message.return_value = {"Messages": []}
    handler.receive_messages(QUEUE_URL, max_messages=20)
    call_kwargs = handler.client.receive_message.call_args.kwargs
    assert call_kwargs["MaxNumberOfMessages"] == 10


# ------------------------------------------------------------------
# delete_message
# ------------------------------------------------------------------


def test_delete_message(handler):
    handler.client.delete_message.return_value = {}
    handler.delete_message(QUEUE_URL, "receipt-handle-abc")
    handler.client.delete_message.assert_called_once_with(
        QueueUrl=QUEUE_URL,
        ReceiptHandle="receipt-handle-abc",
    )


def test_delete_message_raises_on_error(handler):
    handler.client.delete_message.side_effect = ClientError(
        {"Error": {"Code": "ReceiptHandleIsInvalid", "Message": "bad handle"}},
        "DeleteMessage",
    )
    with pytest.raises(ClientError):
        handler.delete_message(QUEUE_URL, "bad-handle")


# ------------------------------------------------------------------
# consume_queue (generator)
# ------------------------------------------------------------------


def test_consume_queue_yields_messages(handler):
    msg1 = {"MessageId": "m1", "Body": '{"a":1}', "ReceiptHandle": "rh1"}
    msg2 = {"MessageId": "m2", "Body": '{"a":2}', "ReceiptHandle": "rh2"}

    # First poll returns 2 messages, second poll returns empty (we break)
    call_count = 0

    def mock_receive(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"Messages": [msg1, msg2]}
        return {}

    handler.client.receive_message.side_effect = mock_receive

    results = []
    for msg in handler.consume_queue(QUEUE_URL):
        results.append(msg)
        if len(results) >= 2:
            break

    assert len(results) == 2
    assert results[0]["MessageId"] == "m1"
    assert results[1]["MessageId"] == "m2"
