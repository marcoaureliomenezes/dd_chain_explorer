"""
Unit tests for OrphanBlocksProcessor (job 2).

Covers:
  - Constructor + logger injection: class instantiates without NameError.
  - recognize_orphaned_blocks: correctly identifies orphan vs safe blocks.
  - handle_orphaned_blocks_cache: writes correct data to block cache.
  - run() happy path: processes messages, re-enqueues orphan.
  - run() error path: non-orphan block is counted and logged at interval.
"""
import importlib.util
import logging
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Load job module
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).parent.parent.parent / "src"
_JOB_FILE = _SRC_DIR / "2_orphan_blocks_watcher.py"


def _load_job():
    spec = importlib.util.spec_from_file_location("job2_orphan_blocks_watcher", _JOB_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_job()
OrphanBlocksProcessor = _mod.OrphanBlocksProcessor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger() -> logging.Logger:
    return logging.getLogger("test.job2")


def _make_processor(
    web3=None,
    sqs=None,
    block_cache=None,
    num_confirmations=3,
    sqs_queue_url="https://sqs.test/mined",
):
    logger = _make_logger()
    proc = OrphanBlocksProcessor(logger)
    proc.src_config({
        "handler_web3": web3 or MagicMock(),
        "num_confirmations": num_confirmations,
        "sqs_handler": sqs or MagicMock(),
        "sqs_queue_url": sqs_queue_url,
    })
    proc.sink_config({
        "block_cache": block_cache or MagicMock(),
    })
    return proc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestOrphanBlocksProcessorConstructor:
    def test_instantiation_does_not_raise(self):
        logger = _make_logger()
        proc = OrphanBlocksProcessor(logger)
        assert proc is not None

    def test_logger_is_stored(self):
        logger = _make_logger()
        proc = OrphanBlocksProcessor(logger)
        assert proc.logger is logger

    def test_no_global_logger_needed(self):
        """Constructor must work even when module-global LOGGER is absent."""
        _mod.__dict__.pop("LOGGER", None)
        logger = _make_logger()
        proc = OrphanBlocksProcessor(logger)
        assert proc.logger is logger


class TestRecognizeOrphanedBlocks:
    def test_returns_true_when_hash_differs(self):
        proc = _make_processor()
        proc.block_cache.get_item.return_value = {"block_hash": "0xOLD"}
        result = proc.recognize_orphaned_blocks(safe_block_number=100, safe_block_hash="0xNEW")
        assert result is True

    def test_returns_false_when_hash_matches(self):
        proc = _make_processor()
        proc.block_cache.get_item.return_value = {"block_hash": "0xSAME"}
        result = proc.recognize_orphaned_blocks(safe_block_number=100, safe_block_hash="0xSAME")
        assert result is False

    def test_returns_false_when_item_not_in_cache(self):
        proc = _make_processor()
        proc.block_cache.get_item.return_value = None
        result = proc.recognize_orphaned_blocks(safe_block_number=100, safe_block_hash="0xANY")
        assert result is False


class TestHandleOrphanedBlocksCache:
    def test_puts_block_to_cache(self):
        proc = _make_processor()
        mined_block = {"value": {"block_number": 77, "block_hash": "0xabc"}}
        proc.handle_orphaned_blocks_cache(mined_block, delay_counter=0)
        proc.block_cache.put_item.assert_called_once_with(
            "BLOCK_CACHE",
            "77",
            attrs={"block_hash": "0xabc"},
            ttl_seconds=3600,
        )


class TestRun:
    """run() happy path and error path."""

    def _sqs_msg(self, block_number: int, block_hash: str) -> dict:
        return {
            "Body": json.dumps({"block_number": block_number, "block_hash": block_hash}),
            "ReceiptHandle": f"receipt-{block_number}",
        }

    def test_run_detects_orphan_and_reenqueues(self):
        """When block hash differs → orphan detected → message re-enqueued."""
        sqs = MagicMock()
        block_cache = MagicMock()
        web3 = MagicMock()

        msg = self._sqs_msg(block_number=500, block_hash="0xOLD")
        sqs.consume_queue.return_value = iter([msg])

        # safe block data from chain
        safe_block = {"number": 497, "hash": "0xNEW", "timestamp": 1700001234}
        web3.extract_block_data.return_value = MagicMock()
        web3.parse_block_data.return_value = safe_block

        # Cache says old hash → orphan
        block_cache.get_item.return_value = {"block_hash": "0xOLD_CACHED"}

        proc = _make_processor(web3=web3, sqs=sqs, block_cache=block_cache)
        proc.run()

        # Must re-enqueue the orphan block event
        sqs.send_message.assert_called_once()
        # Must delete the processed message
        sqs.delete_message.assert_called_once_with(
            "https://sqs.test/mined", f"receipt-500"
        )

    def test_run_safe_block_logs_at_interval(self):
        """Every 10th message: self.logger.info called for safe block confirmation."""
        sqs = MagicMock()
        block_cache = MagicMock()
        web3 = MagicMock()

        # Generate 10 messages (counter 0..9; logger.info triggers at counter==0 mod 10)
        messages = [self._sqs_msg(block_number=i, block_hash=f"0x{i:04x}") for i in range(10)]
        sqs.consume_queue.return_value = iter(messages)

        # Safe block always matching (no orphan)
        def parse_side(raw):
            return {"number": 0, "hash": "0xSAME", "timestamp": 0}
        web3.parse_block_data.side_effect = parse_side
        block_cache.get_item.return_value = {"block_hash": "0xSAME"}

        logger = _make_logger()
        proc = OrphanBlocksProcessor(logger)
        proc.src_config({
            "handler_web3": web3,
            "num_confirmations": 10,
            "sqs_handler": sqs,
            "sqs_queue_url": "https://sqs.test/mined",
        })
        proc.sink_config({"block_cache": block_cache})

        with patch.object(logger, "info") as mock_info:
            proc.run()

        # At counter==0 (first iteration), info should be called
        assert mock_info.called

    def test_run_no_name_error_without_global_logger(self):
        """run() must not raise NameError when module-global LOGGER is absent."""
        _mod.__dict__.pop("LOGGER", None)
        sqs = MagicMock()
        sqs.consume_queue.return_value = iter([])  # no messages → exits immediately
        proc = _make_processor(sqs=sqs)
        proc.run()  # must not raise
