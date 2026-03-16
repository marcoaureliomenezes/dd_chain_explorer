"""
Unit tests for dm_chain_utils.dm_web3_client._convert_hexbytes_to_str.
No network calls required.
"""
import pytest
from hexbytes import HexBytes
from dm_chain_utils.dm_web3_client import _convert_hexbytes_to_str


def test_converts_hexbytes_in_dict():
    data = {"hash": HexBytes("0xdeadbeef"), "value": 42}
    result = _convert_hexbytes_to_str(data)
    assert result["hash"] == "deadbeef"
    assert result["value"] == 42


def test_converts_nested_dict():
    data = {"outer": {"inner": HexBytes("0xabcd")}}
    result = _convert_hexbytes_to_str(data)
    assert result["outer"]["inner"] == "abcd"


def test_converts_list_of_hexbytes():
    data = {"txs": [HexBytes("0x01"), HexBytes("0x02")]}
    result = _convert_hexbytes_to_str(data)
    assert result["txs"] == ["01", "02"]


def test_plain_hexbytes():
    assert _convert_hexbytes_to_str(HexBytes("0xff")) == "ff"


def test_passthrough_non_hexbytes():
    assert _convert_hexbytes_to_str("hello") == "hello"
    assert _convert_hexbytes_to_str(123) == 123
    assert _convert_hexbytes_to_str(None) is None
