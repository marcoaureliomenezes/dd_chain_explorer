"""
Unit tests for BlockDataCrawler (job 3).

Covers:
  - Constructor + logger injection: class instantiates without NameError.
  - batch_txs_hash_ids: sends a batch to SQS, respects threshold.
  - run() happy path: consumes SQS, fetches block, writes to Firehose, batches tx hashes.
  - run() error path: missing block data logs a warning and continues.
"""
import importlib.util
import logging
import json
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Load job module
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).parent.parent.parent / "src"
_JOB_FILE = _SRC_DIR / "3_block_data_crawler.py"


def _load_job():
    spec = importlib.util.spec_from_file_location("job3_block_data_crawler", _JOB_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_job()
BlockDataCrawler = _mod.BlockDataCrawler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger() -> logging.Logger:
    return logging.getLogger("test.job3")


def _make_crawler(
    web3=None,
    sqs_src=None,
    sqs_sink=None,
    firehose=None,
    queue_url_blocks="https://sqs.test/mined",
    queue_url_txs="https://sqs.test/txs",
    firehose_stream="blocks-stream",
    txs_threshold=0,
):
    logger = _make_logger()
    crawler = BlockDataCrawler(logger)
    crawler.src_config({
        "handler_web3": web3 or MagicMock(),
        "sqs_handler": sqs_src or MagicMock(),
        "sqs_queue_url_mined_blocks": queue_url_blocks,
    })
    crawler.sink_config({
        "firehose_handler": firehose or MagicMock(),
        "firehose_stream_blocks": firehose_stream,
        "sqs_handler_sink": sqs_sink or MagicMock(),
        "sqs_queue_url_txs_hash_ids": queue_url_txs,
        "txs_threshold": txs_threshold,
    })
    return crawler


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBlockDataCrawlerConstructor:
    def test_instantiation_does_not_raise(self):
        logger = _make_logger()
        crawler = BlockDataCrawler(logger)
        assert crawler is not None

    def test_logger_is_stored(self):
        logger = _make_logger()
        crawler = BlockDataCrawler(logger)
        assert crawler.logger is logger

    def test_src_config_logs_via_self_logger(self):
        """src_config must call self.logger.info, not a global logger."""
        logger = _make_logger()
        crawler = BlockDataCrawler(logger)
        with patch.object(logger, "info") as mock_info:
            crawler.src_config({
                "handler_web3": MagicMock(),
                "sqs_handler": MagicMock(),
                "sqs_queue_url_mined_blocks": "https://sqs.test/q",
            })
        assert mock_info.called


class TestBatchTxsHashIds:
    def test_sends_batch_when_entries_non_empty(self):
        sqs_sink = MagicMock()
        crawler = _make_crawler(sqs_sink=sqs_sink, txs_threshold=0)
        txs = ["0xaaa", "0xbbb", "0xccc"]
        crawler.batch_txs_hash_ids(txs)
        sqs_sink.send_message_batch.assert_called_once()
        args = sqs_sink.send_message_batch.call_args[0]
        entries = args[1]
        assert len(entries) == 3
        assert json.loads(entries[0]["MessageBody"]) == {"tx_hash": "0xaaa"}

    def test_threshold_truncates_list(self):
        sqs_sink = MagicMock()
        crawler = _make_crawler(sqs_sink=sqs_sink, txs_threshold=2)
        txs = ["0xaaa", "0xbbb", "0xccc", "0xddd"]
        crawler.batch_txs_hash_ids(txs)
        args = sqs_sink.send_message_batch.call_args[0]
        entries = args[1]
        assert len(entries) == 2

    def test_empty_txs_does_not_send(self):
        sqs_sink = MagicMock()
        crawler = _make_crawler(sqs_sink=sqs_sink)
        crawler.batch_txs_hash_ids([])
        sqs_sink.send_message_batch.assert_not_called()


class TestRun:
    def _sqs_msg(self, block_number: int) -> dict:
        return {
            "Body": json.dumps({"block_number": block_number}),
            "ReceiptHandle": f"r-{block_number}",
        }

    def test_run_happy_path_produces_to_firehose(self):
        """A valid block event → block fetched → Firehose put_record → SQS batch of txs."""
        sqs_src = MagicMock()
        sqs_sink = MagicMock()
        firehose = MagicMock()
        web3 = MagicMock()

        msg = self._sqs_msg(99)
        sqs_src.consume_queue.return_value = iter([msg])

        block_data = MagicMock()
        cleaned = {"number": 99, "transactions": ["0xabc", "0xdef"]}
        web3.extract_block_data.return_value = block_data
        web3.parse_block_data.return_value = cleaned

        crawler = _make_crawler(
            web3=web3,
            sqs_src=sqs_src,
            sqs_sink=sqs_sink,
            firehose=firehose,
            txs_threshold=0,
        )
        crawler.run()

        firehose.put_record.assert_called_once()
        call_args = firehose.put_record.call_args
        assert call_args[0][0] == "blocks-stream"
        sqs_sink.send_message_batch.assert_called_once()

    def test_run_missing_block_data_logs_warning_and_skips(self):
        """When block data is None, logs warning via self.logger and continues."""
        sqs_src = MagicMock()
        firehose = MagicMock()
        web3 = MagicMock()

        msg = self._sqs_msg(404)
        sqs_src.consume_queue.return_value = iter([msg])
        web3.extract_block_data.return_value = None  # simulate unavailable block

        logger = _make_logger()
        crawler = BlockDataCrawler(logger)
        crawler.src_config({
            "handler_web3": web3,
            "sqs_handler": sqs_src,
            "sqs_queue_url_mined_blocks": "https://sqs.test/mined",
        })
        crawler.sink_config({
            "firehose_handler": firehose,
            "firehose_stream_blocks": "blocks-stream",
            "sqs_handler_sink": MagicMock(),
            "sqs_queue_url_txs_hash_ids": "https://sqs.test/txs",
            "txs_threshold": 0,
        })

        with patch.object(logger, "warning") as mock_warn:
            crawler.run()

        mock_warn.assert_called_once()
        assert "404" in mock_warn.call_args[0][0]
        firehose.put_record.assert_not_called()

    def test_run_no_name_error_without_global_logger(self):
        """run() works even when module has no LOGGER global defined."""
        _mod.__dict__.pop("LOGGER", None)
        sqs_src = MagicMock()
        sqs_src.consume_queue.return_value = iter([])
        crawler = _make_crawler(sqs_src=sqs_src)
        crawler.run()
