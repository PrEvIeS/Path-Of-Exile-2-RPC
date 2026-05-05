"""Unit tests for domain exceptions (C-4b)."""
from __future__ import annotations


def test_log_stream_stalled_is_poe2rpc_error() -> None:
    from poe2_rpc.domain.exceptions import LogStreamStalled, PoE2RPCError

    assert issubclass(LogStreamStalled, PoE2RPCError)


def test_log_stream_stalled_carries_message() -> None:
    from poe2_rpc.domain.exceptions import LogStreamStalled

    msg = "Failed to enqueue domain line within 2.0s"
    exc = LogStreamStalled(msg)
    assert str(exc) == msg
