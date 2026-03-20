"""
CloudWatch Logs logging handler — replaces KafkaLoggingHandler.

Sends application log records to a CloudWatch Logs log group via boto3,
replacing the previous pattern of publishing logs to a Kafka topic
(``mainnet.0.application.logs``).

Usage:
    from dm_chain_utils.dm_cloudwatch_logger import CloudWatchLoggingHandler

    handler = CloudWatchLoggingHandler(
        log_group="/apps/dm-chain-explorer-prd",
        log_stream="job-1-mined-blocks-watcher",
    )
    logger.addHandler(handler)
    logger.info("Hello from CloudWatch!")

Batching:
    Records are buffered internally and flushed either when the buffer
    reaches ``batch_size`` or when ``flush_interval`` seconds have elapsed
    since the last flush — whichever comes first.  ``emit()`` is
    non-blocking unless the buffer is full.
"""

import json
import logging
import threading
import time

from typing import List, Optional

import boto3
from botocore.exceptions import ClientError


class CloudWatchLoggingHandler(logging.Handler):
    """Python logging handler that sends log records to CloudWatch Logs."""

    def __init__(
        self,
        log_group: str,
        log_stream: str,
        region: str = "sa-east-1",
        batch_size: int = 50,
        flush_interval: float = 5.0,
        create_log_stream: bool = True,
    ):
        """
        Parameters
        ----------
        log_group : str
            CloudWatch Log Group name (must already exist).
        log_stream : str
            Log stream name within the group (created automatically if
            ``create_log_stream=True``).
        region : str
            AWS region.
        batch_size : int
            Max number of log events to buffer before flushing.
        flush_interval : float
            Max seconds between flushes.
        create_log_stream : bool
            If True, creates the log stream on init (idempotent).
        """
        super().__init__()
        self.log_group = log_group
        self.log_stream = log_stream
        self.batch_size = batch_size
        self.flush_interval = flush_interval

        self._client = boto3.client("logs", region_name=region)
        self._buffer: List[dict] = []
        self._lock = threading.Lock()
        self._sequence_token: Optional[str] = None
        self._last_flush = time.time()

        if create_log_stream:
            self._ensure_log_stream()

        # Background flush thread
        self._flush_thread = threading.Thread(
            target=self._periodic_flush, daemon=True
        )
        self._flush_thread.start()

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def _ensure_log_stream(self) -> None:
        """Create the log stream if it does not exist (idempotent)."""
        try:
            self._client.create_log_stream(
                logGroupName=self.log_group,
                logStreamName=self.log_stream,
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
                raise

    # ------------------------------------------------------------------
    # Handler interface
    # ------------------------------------------------------------------

    def emit(self, record: logging.LogRecord) -> None:
        """Buffer a log record for batch delivery to CloudWatch."""
        try:
            message = self.format(record)
            event = {
                "timestamp": int(record.created * 1000),
                "message": message,
            }
            with self._lock:
                self._buffer.append(event)
                if len(self._buffer) >= self.batch_size:
                    self._flush_locked()
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        """Force-flush the internal buffer to CloudWatch."""
        with self._lock:
            self._flush_locked()

    def close(self) -> None:
        """Flush remaining records and close the handler."""
        self.flush()
        super().close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _flush_locked(self) -> None:
        """Send buffered events to CloudWatch. Must be called while holding ``_lock``."""
        if not self._buffer:
            return

        # CloudWatch requires events sorted by timestamp
        events = sorted(self._buffer, key=lambda e: e["timestamp"])
        self._buffer = []
        self._last_flush = time.time()

        kwargs = {
            "logGroupName": self.log_group,
            "logStreamName": self.log_stream,
            "logEvents": events,
        }
        if self._sequence_token:
            kwargs["sequenceToken"] = self._sequence_token

        try:
            response = self._client.put_log_events(**kwargs)
            self._sequence_token = response.get("nextSequenceToken")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code in (
                "InvalidSequenceTokenException",
                "DataAlreadyAcceptedException",
            ):
                # Fetch the correct token and retry once
                self._sequence_token = e.response["Error"]["Message"].split()[-1]
                if self._sequence_token == "null":
                    self._sequence_token = None
                kwargs["sequenceToken"] = self._sequence_token
                try:
                    response = self._client.put_log_events(**kwargs)
                    self._sequence_token = response.get("nextSequenceToken")
                except Exception:
                    pass  # best effort — avoid crashing the application
            else:
                pass  # best effort

    def _periodic_flush(self) -> None:
        """Background thread that flushes the buffer at regular intervals."""
        while True:
            time.sleep(self.flush_interval)
            with self._lock:
                if self._buffer and (time.time() - self._last_flush) >= self.flush_interval:
                    self._flush_locked()
