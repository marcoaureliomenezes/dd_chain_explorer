"""
Kinesis Data Streams handler — put/get records via boto3.

Replaces dm_kafka_client.py for data streams that need S3 delivery via Firehose.
Used by streaming jobs for topics:
  - mainnet.2.blocks.data        → Kinesis stream mainnet-blocks-data
  - mainnet.4.transactions.data  → Kinesis stream mainnet-transactions-data
  - mainnet.5.transactions.input_decoded → Kinesis stream mainnet-transactions-decoded

Usage:
    from dm_chain_utils.dm_kinesis import KinesisHandler

    kinesis = KinesisHandler(logger)
    kinesis.put_record("mainnet-blocks-data-prd", data=json.dumps(block), partition_key=str(block_number))

    # Consumer (polling):
    for record in kinesis.consume_stream("mainnet-transactions-data-prd"):
        tx = json.loads(record["Data"])
        ...
"""

import json
import logging
import time

from typing import Any, Dict, Generator, List, Optional

import boto3
from botocore.exceptions import ClientError


class KinesisHandler:
    """Thin wrapper around boto3 Kinesis client for producing and consuming records."""

    def __init__(self, logger: logging.Logger, region: str = "sa-east-1"):
        self.logger = logger
        self.client = boto3.client("kinesis", region_name=region)

    # ------------------------------------------------------------------
    # Producer methods
    # ------------------------------------------------------------------

    def put_record(
        self,
        stream_name: str,
        data: str,
        partition_key: str,
    ) -> Dict[str, Any]:
        """Put a single record into a Kinesis stream.

        Parameters
        ----------
        stream_name : str
            Name of the Kinesis Data Stream.
        data : str
            Record payload (typically ``json.dumps(...)``).
        partition_key : str
            Determines which shard receives the record.

        Returns
        -------
        dict
            Kinesis PutRecord response (contains ShardId, SequenceNumber).
        """
        try:
            # Append newline so Firehose produces valid NDJSON files in S3
            payload = data if isinstance(data, str) else data.decode("utf-8")
            if not payload.endswith("\n"):
                payload += "\n"
            response = self.client.put_record(
                StreamName=stream_name,
                Data=payload.encode("utf-8"),
                PartitionKey=partition_key,
            )
            self.logger.debug(
                f"Kinesis_PutRecord;STREAM:{stream_name};SHARD:{response['ShardId']};"
                f"SEQ:{response['SequenceNumber']};KEY:{partition_key}"
            )
            return response
        except ClientError as e:
            self.logger.error(f"Kinesis PutRecord failed: {e}")
            raise

    def put_records(
        self,
        stream_name: str,
        records: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Put multiple records into a Kinesis stream in a single batch call.

        Parameters
        ----------
        stream_name : str
            Name of the Kinesis Data Stream.
        records : list[dict]
            Each dict must have keys ``Data`` (str) and ``PartitionKey`` (str).

        Returns
        -------
        dict
            Kinesis PutRecords response.
        """
        entries = [
            {
                "Data": r["Data"].encode("utf-8") if isinstance(r["Data"], str) else r["Data"],
                "PartitionKey": r["PartitionKey"],
            }
            for r in records
        ]
        try:
            response = self.client.put_records(
                StreamName=stream_name,
                Records=entries,
            )
            failed = response.get("FailedRecordCount", 0)
            if failed > 0:
                self.logger.warning(
                    f"Kinesis PutRecords: {failed}/{len(entries)} records failed for {stream_name}"
                )
            else:
                self.logger.debug(
                    f"Kinesis_PutRecords;STREAM:{stream_name};COUNT:{len(entries)}"
                )
            return response
        except ClientError as e:
            self.logger.error(f"Kinesis PutRecords failed: {e}")
            raise

    # ------------------------------------------------------------------
    # Consumer methods
    # ------------------------------------------------------------------

    def get_shard_iterator(
        self,
        stream_name: str,
        shard_id: str = "shardId-000000000000",
        iterator_type: str = "LATEST",
        starting_sequence_number: Optional[str] = None,
    ) -> str:
        """Get a shard iterator for reading records from a specific shard.

        Parameters
        ----------
        iterator_type : str
            One of LATEST, TRIM_HORIZON, AT_SEQUENCE_NUMBER, AFTER_SEQUENCE_NUMBER.
        """
        kwargs: Dict[str, Any] = {
            "StreamName": stream_name,
            "ShardId": shard_id,
            "ShardIteratorType": iterator_type,
        }
        if starting_sequence_number and iterator_type in (
            "AT_SEQUENCE_NUMBER",
            "AFTER_SEQUENCE_NUMBER",
        ):
            kwargs["StartingSequenceNumber"] = starting_sequence_number

        response = self.client.get_shard_iterator(**kwargs)
        return response["ShardIterator"]

    def get_records(
        self,
        shard_iterator: str,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Fetch records using a shard iterator.

        Returns
        -------
        dict with keys ``Records`` (list) and ``NextShardIterator`` (str).
        """
        response = self.client.get_records(
            ShardIterator=shard_iterator,
            Limit=limit,
        )
        return response

    def consume_stream(
        self,
        stream_name: str,
        shard_id: str = "shardId-000000000000",
        iterator_type: str = "LATEST",
        poll_interval: float = 0.5,
        batch_size: int = 100,
    ) -> Generator[Dict[str, Any], None, None]:
        """Infinite generator that polls a Kinesis shard and yields records.

        Each yielded item is a dict with keys:
          - ``Data`` (bytes): raw record payload
          - ``PartitionKey`` (str)
          - ``SequenceNumber`` (str)
          - ``ApproximateArrivalTimestamp`` (datetime)

        The generator handles iterator expiration by re-fetching a new iterator.
        """
        shard_iterator = self.get_shard_iterator(
            stream_name, shard_id, iterator_type
        )

        while True:
            try:
                resp = self.get_records(shard_iterator, limit=batch_size)
            except ClientError as e:
                error_code = e.response["Error"]["Code"]
                if error_code == "ExpiredIteratorException":
                    self.logger.warning(
                        f"Kinesis iterator expired for {stream_name}/{shard_id}. Re-fetching."
                    )
                    shard_iterator = self.get_shard_iterator(
                        stream_name, shard_id, iterator_type
                    )
                    continue
                if error_code == "ProvisionedThroughputExceededException":
                    self.logger.warning("Kinesis read throttled. Backing off 1s.")
                    time.sleep(1)
                    continue
                raise

            records = resp.get("Records", [])
            for record in records:
                yield record

            shard_iterator = resp.get("NextShardIterator")
            if not shard_iterator:
                self.logger.info(f"Shard {shard_id} of {stream_name} is closed.")
                break

            if not records:
                time.sleep(poll_interval)
