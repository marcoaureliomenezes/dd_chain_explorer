"""
SQS handler — send/receive/delete messages via boto3.

Replaces dm_kafka_client.py for inter-job communication topics:
  - mainnet.1.mined_blocks.events  → SQS queue mainnet-mined-blocks-events
  - mainnet.3.block.txs.hash_id    → SQS queue mainnet-block-txs-hash-id

Usage:
    from dm_chain_utils.dm_sqs import SQSHandler

    sqs = SQSHandler(logger)
    sqs.send_message(queue_url, json.dumps({"block_number": 123, ...}))

    # Consumer (long-polling):
    for msg in sqs.consume_queue(queue_url):
        data = json.loads(msg["Body"])
        # ... process ...
        sqs.delete_message(queue_url, msg["ReceiptHandle"])
"""

import json
import logging
import time
import uuid

from typing import Any, Dict, Generator, List, Optional

import boto3
from botocore.exceptions import ClientError


class SQSHandler:
    """Thin wrapper around boto3 SQS client for producing and consuming messages."""

    def __init__(self, logger: logging.Logger, region: str = "sa-east-1"):
        self.logger = logger
        self.client = boto3.client("sqs", region_name=region)

    # ------------------------------------------------------------------
    # Producer methods
    # ------------------------------------------------------------------

    def send_message(
        self,
        queue_url: str,
        message_body: str,
        message_attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a single message to an SQS queue.

        Parameters
        ----------
        queue_url : str
            The URL of the SQS queue.
        message_body : str
            The message payload (typically ``json.dumps(...)``).
        message_attributes : dict, optional
            SQS message attributes for filtering/routing.

        Returns
        -------
        dict
            SQS SendMessage response (contains MessageId, MD5OfMessageBody).
        """
        kwargs: Dict[str, Any] = {
            "QueueUrl": queue_url,
            "MessageBody": message_body,
        }
        if message_attributes:
            kwargs["MessageAttributes"] = message_attributes

        try:
            response = self.client.send_message(**kwargs)
            self.logger.debug(
                f"SQS_SendMessage;QUEUE:{queue_url.split('/')[-1]};MSG_ID:{response['MessageId']}"
            )
            return response
        except ClientError as e:
            self.logger.error(f"SQS SendMessage failed: {e}")
            raise

    def send_message_batch(
        self,
        queue_url: str,
        entries: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Send up to 10 messages in a single batch call.

        Parameters
        ----------
        queue_url : str
            The URL of the SQS queue.
        entries : list[dict]
            Each dict must have key ``MessageBody`` (str).
            Optionally ``Id`` (str) — auto-generated if absent.

        Returns
        -------
        dict
            SQS SendMessageBatch response.
        """
        batch_entries = []
        for i, entry in enumerate(entries):
            batch_entries.append({
                "Id": entry.get("Id", str(i)),
                "MessageBody": entry["MessageBody"],
            })

        # SQS batch limit is 10 messages
        all_successful = []
        all_failed = []
        for chunk_start in range(0, len(batch_entries), 10):
            chunk = batch_entries[chunk_start : chunk_start + 10]
            try:
                response = self.client.send_message_batch(
                    QueueUrl=queue_url,
                    Entries=chunk,
                )
                all_successful.extend(response.get("Successful", []))
                failed = response.get("Failed", [])
                if failed:
                    self.logger.warning(
                        f"SQS SendMessageBatch: {len(failed)} messages failed"
                    )
                    all_failed.extend(failed)
            except ClientError as e:
                self.logger.error(f"SQS SendMessageBatch failed: {e}")
                raise

        self.logger.debug(
            f"SQS_SendMessageBatch;QUEUE:{queue_url.split('/')[-1]};"
            f"OK:{len(all_successful)};FAIL:{len(all_failed)}"
        )
        return {"Successful": all_successful, "Failed": all_failed}

    # ------------------------------------------------------------------
    # Consumer methods
    # ------------------------------------------------------------------

    def receive_messages(
        self,
        queue_url: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
        visibility_timeout: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Receive messages from an SQS queue (single poll).

        Uses long polling by default (``wait_time_seconds=20``).

        Returns
        -------
        list[dict]
            List of SQS messages. Each has keys: MessageId, ReceiptHandle, Body, etc.
        """
        kwargs: Dict[str, Any] = {
            "QueueUrl": queue_url,
            "MaxNumberOfMessages": min(max_messages, 10),
            "WaitTimeSeconds": wait_time_seconds,
        }
        if visibility_timeout is not None:
            kwargs["VisibilityTimeout"] = visibility_timeout

        try:
            response = self.client.receive_message(**kwargs)
            messages = response.get("Messages", [])
            if messages:
                self.logger.debug(
                    f"SQS_ReceiveMessage;QUEUE:{queue_url.split('/')[-1]};COUNT:{len(messages)}"
                )
            return messages
        except ClientError as e:
            self.logger.error(f"SQS ReceiveMessage failed: {e}")
            raise

    def delete_message(self, queue_url: str, receipt_handle: str) -> None:
        """Delete a message from an SQS queue after successful processing.

        Parameters
        ----------
        queue_url : str
            The URL of the SQS queue.
        receipt_handle : str
            The receipt handle from the received message.
        """
        try:
            self.client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=receipt_handle,
            )
            self.logger.debug(
                f"SQS_DeleteMessage;QUEUE:{queue_url.split('/')[-1]}"
            )
        except ClientError as e:
            self.logger.error(f"SQS DeleteMessage failed: {e}")
            raise

    def delete_message_batch(
        self,
        queue_url: str,
        entries: List[Dict[str, str]],
    ) -> None:
        """Delete multiple messages from an SQS queue in a single batch call.

        Parameters
        ----------
        entries : list[dict]
            Each dict must have keys ``Id`` (str) and ``ReceiptHandle`` (str).
        """
        for chunk_start in range(0, len(entries), 10):
            chunk = entries[chunk_start : chunk_start + 10]
            try:
                self.client.delete_message_batch(
                    QueueUrl=queue_url,
                    Entries=chunk,
                )
            except ClientError as e:
                self.logger.error(f"SQS DeleteMessageBatch failed: {e}")
                raise

    # ------------------------------------------------------------------
    # Convenience: infinite consumer generator
    # ------------------------------------------------------------------

    def consume_queue(
        self,
        queue_url: str,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
    ) -> Generator[Dict[str, Any], None, None]:
        """Infinite generator that long-polls an SQS queue and yields messages.

        Each yielded item is a raw SQS message dict with keys:
          - ``MessageId`` (str)
          - ``ReceiptHandle`` (str)
          - ``Body`` (str): the message payload
          - ``MD5OfBody`` (str)

        **Important**: The caller must call ``delete_message()`` after processing
        each message to prevent re-delivery.
        """
        while True:
            messages = self.receive_messages(
                queue_url,
                max_messages=max_messages,
                wait_time_seconds=wait_time_seconds,
            )
            for msg in messages:
                yield msg
