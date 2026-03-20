"""
Unit tests for dm_chain_utils.dm_cloudwatch_logger.CloudWatchLoggingHandler.
All boto3 calls are mocked — no AWS credentials required.
"""
import logging
import time
from unittest.mock import MagicMock, patch, call

import pytest
from botocore.exceptions import ClientError

from dm_chain_utils.dm_cloudwatch_logger import CloudWatchLoggingHandler


@pytest.fixture
def mock_client():
    with patch("dm_chain_utils.dm_cloudwatch_logger.boto3") as mock_boto3:
        client = MagicMock()
        mock_boto3.client.return_value = client
        client.create_log_stream.return_value = {}
        client.put_log_events.return_value = {"nextSequenceToken": "token-1"}
        yield client


@pytest.fixture
def handler(mock_client):
    h = CloudWatchLoggingHandler(
        log_group="/test/group",
        log_stream="test-stream",
        region="us-east-1",
        batch_size=5,
        flush_interval=60.0,  # large interval so periodic flush doesn't interfere
        create_log_stream=True,
    )
    h.setFormatter(logging.Formatter("%(message)s"))
    yield h
    h.close()


# ------------------------------------------------------------------
# Initialization
# ------------------------------------------------------------------


def test_creates_log_stream_on_init(mock_client, handler):
    mock_client.create_log_stream.assert_called_once_with(
        logGroupName="/test/group",
        logStreamName="test-stream",
    )


def test_create_log_stream_idempotent(mock_client):
    mock_client.create_log_stream.side_effect = ClientError(
        {"Error": {"Code": "ResourceAlreadyExistsException", "Message": "exists"}},
        "CreateLogStream",
    )
    # Should not raise
    h = CloudWatchLoggingHandler(
        log_group="/test/group",
        log_stream="test-stream",
        region="us-east-1",
        batch_size=5,
        flush_interval=60.0,
        create_log_stream=True,
    )
    h.close()


def test_create_log_stream_raises_other_errors(mock_client):
    mock_client.create_log_stream.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "group not found"}},
        "CreateLogStream",
    )
    with pytest.raises(ClientError):
        CloudWatchLoggingHandler(
            log_group="/nonexistent/group",
            log_stream="test-stream",
            region="us-east-1",
            create_log_stream=True,
        )


# ------------------------------------------------------------------
# emit + flush
# ------------------------------------------------------------------


def test_emit_buffers_records(mock_client, handler):
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello", args=(), exc_info=None,
    )
    handler.emit(record)

    # Should be buffered, not flushed yet (batch_size=5)
    mock_client.put_log_events.assert_not_called()


def test_flush_sends_buffered_events(mock_client, handler):
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="test message", args=(), exc_info=None,
    )
    handler.emit(record)
    handler.flush()

    mock_client.put_log_events.assert_called_once()
    call_kwargs = mock_client.put_log_events.call_args.kwargs
    assert call_kwargs["logGroupName"] == "/test/group"
    assert call_kwargs["logStreamName"] == "test-stream"
    assert len(call_kwargs["logEvents"]) == 1
    assert call_kwargs["logEvents"][0]["message"] == "test message"


def test_auto_flush_at_batch_size(mock_client, handler):
    for i in range(5):
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=f"msg-{i}", args=(), exc_info=None,
        )
        handler.emit(record)

    # batch_size=5, so should have auto-flushed
    mock_client.put_log_events.assert_called_once()
    call_kwargs = mock_client.put_log_events.call_args.kwargs
    assert len(call_kwargs["logEvents"]) == 5


def test_flush_empty_buffer_is_noop(mock_client, handler):
    handler.flush()
    mock_client.put_log_events.assert_not_called()


def test_events_sorted_by_timestamp(mock_client, handler):
    # Emit records with different timestamps
    for ts in [3000, 1000, 2000]:
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg=f"ts-{ts}", args=(), exc_info=None,
        )
        record.created = ts / 1000.0
        handler.emit(record)

    handler.flush()
    call_kwargs = mock_client.put_log_events.call_args.kwargs
    timestamps = [e["timestamp"] for e in call_kwargs["logEvents"]]
    assert timestamps == sorted(timestamps)


# ------------------------------------------------------------------
# Sequence token handling
# ------------------------------------------------------------------


def test_stores_sequence_token(mock_client, handler):
    mock_client.put_log_events.return_value = {"nextSequenceToken": "tok-abc"}
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="msg", args=(), exc_info=None,
    )
    handler.emit(record)
    handler.flush()

    assert handler._sequence_token == "tok-abc"

    # Second flush should pass the token
    handler.emit(record)
    handler.flush()
    call_kwargs = mock_client.put_log_events.call_args.kwargs
    assert call_kwargs.get("sequenceToken") == "tok-abc"


def test_handles_invalid_sequence_token(mock_client, handler):
    mock_client.put_log_events.side_effect = [
        ClientError(
            {"Error": {
                "Code": "InvalidSequenceTokenException",
                "Message": "The given sequenceToken is invalid. The next expected sequenceToken is: correct-token",
            }},
            "PutLogEvents",
        ),
        {"nextSequenceToken": "new-token"},
    ]
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="retry msg", args=(), exc_info=None,
    )
    handler.emit(record)
    handler.flush()

    # Should have retried and updated token
    assert mock_client.put_log_events.call_count == 2


# ------------------------------------------------------------------
# close
# ------------------------------------------------------------------


def test_close_flushes_remaining(mock_client, handler):
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="final", args=(), exc_info=None,
    )
    handler.emit(record)
    handler.close()

    mock_client.put_log_events.assert_called_once()
