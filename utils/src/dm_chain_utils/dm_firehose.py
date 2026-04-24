"""
Firehose Direct Put handler — put records directly to a Firehose delivery stream.

Used by streaming jobs that previously wrote to Kinesis streams that no longer
exist (mainnet-blocks-data, mainnet-transactions-decoded). The app now writes
directly to Firehose, which delivers to S3 without an intermediate Kinesis stream.

Usage:
    from dm_chain_utils.dm_firehose import FirehoseHandler

    firehose = FirehoseHandler(logger)
    firehose.put_record("firehose-mainnet-blocks-data-prd", data=json.dumps(block))
"""

import logging

from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError


class FirehoseHandler:
    """Thin wrapper around boto3 Firehose client for Direct Put delivery."""

    def __init__(self, logger: logging.Logger, region: str = "sa-east-1"):
        self.logger = logger
        self.client = boto3.client("firehose", region_name=region)

    def put_record(
        self,
        delivery_stream_name: str,
        data: str,
    ) -> Dict[str, Any]:
        """Put a single record into a Firehose delivery stream.

        Parameters
        ----------
        delivery_stream_name : str
            Name of the Firehose delivery stream.
        data : str
            Record payload (typically ``json.dumps(...)``).

        Returns
        -------
        dict
            Firehose PutRecord response (contains RecordId).
        """
        try:
            payload = data if isinstance(data, str) else data.decode("utf-8")
            if not payload.endswith("\n"):
                payload += "\n"
            response = self.client.put_record(
                DeliveryStreamName=delivery_stream_name,
                Record={"Data": payload.encode("utf-8")},
            )
            self.logger.debug(
                f"Firehose_PutRecord;STREAM:{delivery_stream_name};RECORD_ID:{response['RecordId']}"
            )
            return response
        except ClientError as e:
            self.logger.error(f"Firehose PutRecord failed: {e}")
            raise

    def put_record_batch(
        self,
        delivery_stream_name: str,
        records: list,
    ) -> Dict[str, Any]:
        """Put up to 500 records in a single batch call.

        Parameters
        ----------
        records : list[str]
            List of string payloads to deliver.
        """
        entries = []
        for r in records:
            payload = r if isinstance(r, str) else r.decode("utf-8")
            if not payload.endswith("\n"):
                payload += "\n"
            entries.append({"Data": payload.encode("utf-8")})

        try:
            response = self.client.put_record_batch(
                DeliveryStreamName=delivery_stream_name,
                Records=entries,
            )
            failed = response.get("FailedPutCount", 0)
            if failed > 0:
                self.logger.warning(
                    f"Firehose PutRecordBatch: {failed}/{len(entries)} records failed for {delivery_stream_name}"
                )
            else:
                self.logger.debug(
                    f"Firehose_PutRecordBatch;STREAM:{delivery_stream_name};COUNT:{len(entries)}"
                )
            return response
        except ClientError as e:
            self.logger.error(f"Firehose PutRecordBatch failed: {e}")
            raise
