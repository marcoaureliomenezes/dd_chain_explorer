"""
Unit tests for TransactionInputDecoder (job 5).

Covers:
  - Constructor + logger injection: class instantiates without NameError.
  - _build_record: normalizes decode_type and decode_confidence correctly.
  - _decode_input happy path: returns full decode from ABI cache.
  - _decode_input: falls back to 4byte.directory when cache misses.
  - run() happy path: consumes Kinesis, decodes, produces to Firehose.
  - run() error path: skips contract deploys and plain ETH transfers.
"""
import importlib.util
import logging
import json
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

# ---------------------------------------------------------------------------
# Load job module
# ---------------------------------------------------------------------------
_SRC_DIR = Path(__file__).parent.parent.parent / "src"
_JOB_FILE = _SRC_DIR / "5_txs_input_decoder.py"


def _load_job():
    spec = importlib.util.spec_from_file_location("job5_txs_input_decoder", _JOB_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_mod = _load_job()
TransactionInputDecoder = _mod.TransactionInputDecoder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_logger() -> logging.Logger:
    return logging.getLogger("test.job5")


def _make_decoder(
    abi_cache=None,
    etherscan=None,
    kinesis=None,
    firehose=None,
    stream_in="mainnet.4.txs",
    firehose_out="mainnet.5.decoded",
):
    logger = _make_logger()
    cache = abi_cache or MagicMock()
    eth = etherscan or MagicMock()
    decoder = TransactionInputDecoder(logger, cache, eth)
    decoder.src_config({
        "kinesis_handler": kinesis or MagicMock(),
        "stream_in": stream_in,
    })
    decoder.sink_config({
        "firehose_handler": firehose or MagicMock(),
        "firehose_out": firehose_out,
    })
    return decoder


def _make_tx(
    tx_hash="0xdeadbeef",
    to="0xcontract",
    input_hex="0xa9059cbb" + "00" * 64,  # ERC-20 transfer selector + padding
) -> dict:
    return {"hash": tx_hash, "to": to, "input": input_hex}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestTransactionInputDecoderConstructor:
    def test_instantiation_does_not_raise(self):
        logger = _make_logger()
        decoder = TransactionInputDecoder(logger, MagicMock(), MagicMock())
        assert decoder is not None

    def test_logger_is_stored(self):
        logger = _make_logger()
        decoder = TransactionInputDecoder(logger, MagicMock(), MagicMock())
        assert decoder.logger is logger

    def test_no_global_logger_needed(self):
        _mod.__dict__.pop("LOGGER", None)
        logger = _make_logger()
        decoder = TransactionInputDecoder(logger, MagicMock(), MagicMock())
        assert decoder.logger is logger

    def test_counters_initialized_to_zero(self):
        logger = _make_logger()
        decoder = TransactionInputDecoder(logger, MagicMock(), MagicMock())
        assert decoder._cnt_cache_hit == 0
        assert decoder._cnt_api_call == 0


class TestBuildRecord:
    """_build_record normalizes decode types and fields."""

    def _decoder(self):
        return _make_decoder()

    def test_full_decode_type_maps_to_abi(self):
        d = self._decoder()
        tx = _make_tx()
        result = {"method": "transfer", "parms": {"to": "0xabc"}, "decode_type": "full", "decode_source": "abi_cache"}
        rec = d._build_record(tx, "0xcontract", result)
        assert rec["decode_type"] == "abi"
        assert rec["decode_confidence"] == "full"

    def test_full_4byte_maps_to_4byte_full(self):
        d = self._decoder()
        tx = _make_tx()
        result = {"method": "swap", "parms": {}, "decode_type": "full_4byte", "decode_source": "4byte_directory"}
        rec = d._build_record(tx, "0xcontract", result)
        assert rec["decode_type"] == "4byte"
        assert rec["decode_confidence"] == "full"

    def test_partial_decode_maps_to_4byte_partial(self):
        d = self._decoder()
        tx = _make_tx()
        result = {"method": "swap", "parms": {}, "decode_type": "partial", "decode_source": "4byte_directory"}
        rec = d._build_record(tx, "0xcontract", result)
        assert rec["decode_type"] == "4byte"
        assert rec["decode_confidence"] == "partial"

    def test_unknown_decode(self):
        d = self._decoder()
        tx = _make_tx()
        result = {"method": "0xa9059cbb", "parms": {}, "decode_type": "unknown", "decode_source": "unknown"}
        rec = d._build_record(tx, "0xcontract", result)
        assert rec["decode_type"] == "unknown"
        assert rec["decode_confidence"] == "none"

    def test_method_id_extracted_from_input(self):
        d = self._decoder()
        tx = _make_tx(input_hex="0xa9059cbb" + "00" * 64)
        result = {"method": "transfer", "parms": {}, "decode_type": "full", "decode_source": "abi_cache"}
        rec = d._build_record(tx, "0xcontract", result)
        assert rec["method_id"] == "0xa9059cbb"

    def test_parms_serialized_to_json_string(self):
        d = self._decoder()
        tx = _make_tx()
        parms = {"to": "0xabc", "value": 1000}
        result = {"method": "transfer", "parms": parms, "decode_type": "full", "decode_source": "abi_cache"}
        rec = d._build_record(tx, "0xcontract", result)
        assert rec["parms"] == json.dumps(parms)


class TestDecodeInput:
    """_decode_input pipeline: cache → etherscan → 4byte → unknown."""

    def test_cache_hit_returns_full_decode(self):
        """If ABI cache has the ABI, returns full decode without calling etherscan."""
        cache = MagicMock()
        eth = MagicMock()
        decoder = _make_decoder(abi_cache=cache, etherscan=eth)

        # Mock _decode_with_abi to return a decoded result
        decoded_result = {"method": "transfer", "parms": {}, "decode_type": "full"}
        cache.get.return_value = [{"name": "transfer"}]  # ABI hit
        cache.is_unverified.return_value = False

        with patch.object(decoder, "_decode_with_abi", return_value=decoded_result):
            result = decoder._decode_input("0xcontract", "0xa9059cbb" + "00" * 64)

        assert result["method"] == "transfer"
        assert result["decode_source"] == "abi_cache"
        eth.fetch_contract_abi.assert_not_called()

    def test_etherscan_fetched_when_cache_misses(self):
        """Cache miss → etherscan API called."""
        cache = MagicMock()
        eth = MagicMock()
        decoder = _make_decoder(abi_cache=cache, etherscan=eth)

        cache.get.return_value = None
        cache.is_unverified.return_value = False
        eth.fetch_contract_abi.return_value = [{"name": "transfer"}]
        eth.get_4byte_signature.return_value = None

        decoded_result = {"method": "transfer", "parms": {}, "decode_type": "full"}
        with patch.object(decoder, "_decode_with_abi", return_value=decoded_result):
            result = decoder._decode_input("0xcontract", "0xa9059cbb" + "00" * 64)

        eth.fetch_contract_abi.assert_called_once()
        assert result["decode_source"] == "etherscan_api"

    def test_4byte_fallback_when_etherscan_returns_none(self):
        """Etherscan returns no ABI → 4byte fallback used."""
        cache = MagicMock()
        eth = MagicMock()
        decoder = _make_decoder(abi_cache=cache, etherscan=eth)

        cache.get.return_value = None
        cache.is_unverified.return_value = False
        eth.fetch_contract_abi.return_value = None
        eth.get_4byte_signature.return_value = "transfer(address,uint256)"

        with patch.object(decoder, "_decode_with_sig", return_value={"method": "transfer", "parms": {}, "decode_type": "partial"}):
            result = decoder._decode_input("0xcontract", "0xa9059cbb" + "00" * 64)

        assert result["decode_source"] == "4byte_directory"

    def test_unknown_when_all_sources_fail(self):
        """All sources fail → returns unknown decode."""
        cache = MagicMock()
        eth = MagicMock()
        decoder = _make_decoder(abi_cache=cache, etherscan=eth)

        cache.get.return_value = None
        cache.is_unverified.return_value = True  # negative cache → skip etherscan
        eth.get_4byte_signature.return_value = None

        result = decoder._decode_input("0xcontract", "0xa9059cbb" + "00" * 64)
        assert result["decode_type"] == "unknown"


class TestRun:
    """run() happy path and skip conditions."""

    def _kinesis_record(self, tx: dict) -> dict:
        return {"Data": json.dumps(tx).encode()}

    def test_run_happy_path_produces_to_firehose(self):
        """Valid contract-call tx → decoded → Firehose put_record called."""
        kinesis = MagicMock()
        firehose = MagicMock()
        cache = MagicMock()
        eth = MagicMock()

        tx = _make_tx(input_hex="0xa9059cbb" + "00" * 64)
        kinesis.consume_stream.return_value = iter([self._kinesis_record(tx)])

        cache.stats.return_value = {"cached_abis": 0, "unverified_addresses": 0}
        cache.get.return_value = None
        cache.is_unverified.return_value = False
        eth.fetch_contract_abi.return_value = None
        eth.get_4byte_signature.return_value = "transfer(address,uint256)"

        decoder = _make_decoder(abi_cache=cache, etherscan=eth, kinesis=kinesis, firehose=firehose)

        with patch.object(decoder, "_decode_with_sig", return_value={"method": "transfer", "parms": {}, "decode_type": "partial"}):
            decoder.run()

        firehose.put_record.assert_called_once()

    def test_run_skips_contract_deploys(self):
        """Tx with to=None (contract deploy) must be skipped."""
        kinesis = MagicMock()
        firehose = MagicMock()
        cache = MagicMock()

        tx = _make_tx(to=None)  # deploy
        kinesis.consume_stream.return_value = iter([self._kinesis_record(tx)])
        cache.stats.return_value = {"cached_abis": 0, "unverified_addresses": 0}

        decoder = _make_decoder(abi_cache=cache, kinesis=kinesis, firehose=firehose)
        decoder.run()

        firehose.put_record.assert_not_called()

    def test_run_skips_plain_eth_transfers(self):
        """Tx with input='0x' must be skipped (plain ETH transfer)."""
        kinesis = MagicMock()
        firehose = MagicMock()
        cache = MagicMock()

        tx = _make_tx(input_hex="0x")
        kinesis.consume_stream.return_value = iter([self._kinesis_record(tx)])
        cache.stats.return_value = {"cached_abis": 0, "unverified_addresses": 0}

        decoder = _make_decoder(abi_cache=cache, kinesis=kinesis, firehose=firehose)
        decoder.run()

        firehose.put_record.assert_not_called()

    def test_run_skips_unknown_decodes(self):
        """Tx where all decode sources fail → decode_type=unknown → skipped."""
        kinesis = MagicMock()
        firehose = MagicMock()
        cache = MagicMock()
        eth = MagicMock()

        tx = _make_tx(input_hex="0xdeadbeef" + "00" * 64)
        kinesis.consume_stream.return_value = iter([self._kinesis_record(tx)])
        cache.stats.return_value = {"cached_abis": 0, "unverified_addresses": 0}
        cache.get.return_value = None
        cache.is_unverified.return_value = True
        eth.get_4byte_signature.return_value = None

        decoder = _make_decoder(abi_cache=cache, etherscan=eth, kinesis=kinesis, firehose=firehose)
        decoder.run()

        firehose.put_record.assert_not_called()

    def test_run_no_name_error_without_global_logger(self):
        """run() must not raise NameError when module has no LOGGER global."""
        _mod.__dict__.pop("LOGGER", None)
        kinesis = MagicMock()
        cache = MagicMock()
        kinesis.consume_stream.return_value = iter([])
        cache.stats.return_value = {"cached_abis": 0, "unverified_addresses": 0}
        decoder = _make_decoder(abi_cache=cache, kinesis=kinesis)
        decoder.run()


class TestF03ExceptionLogging:
    """F-03 (CWE-755): broad except blocks must log before returning None."""

    def test_build_record_logs_warning_on_exception(self):
        """_build_record must log a warning via self.logger when it raises internally."""
        logger = _make_logger()
        decoder = TransactionInputDecoder(logger, MagicMock(), MagicMock())

        # Pass a result dict missing the required 'decode_type' key to trigger KeyError
        bad_result = {}  # missing 'decode_type' → KeyError inside _build_record
        tx = _make_tx()

        with patch.object(logger, "warning") as mock_warn:
            rec = decoder._build_record(tx, "0xcontract", bad_result)

        assert rec is None
        mock_warn.assert_called_once()
        assert "build_record" in mock_warn.call_args[0][0]

    def test_decode_with_abi_logs_warning_on_exception(self):
        """_decode_with_abi must log a warning via self.logger when ABI decode fails."""
        logger = _make_logger()
        decoder = TransactionInputDecoder(logger, MagicMock(), MagicMock())

        # Pass an invalid ABI and input to trigger an exception in decode_function_input.
        # _get_contract is lru_cache'd and uses web3 mock; we make it raise.
        with patch.object(decoder, "_get_contract", side_effect=Exception("abi decode error")):
            with patch.object(logger, "warning") as mock_warn:
                result = decoder._decode_with_abi("0xcontract", [{"name": "transfer"}], "0xa9059cbb00")

        assert result is None
        mock_warn.assert_called_once()
        assert "ABI decode failed" in mock_warn.call_args[0][0]
