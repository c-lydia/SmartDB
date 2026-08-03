from __future__ import annotations

import threading
from dataclasses import dataclass

@dataclass(frozen=True)
class StoreResult:
    status: str

@dataclass(frozen=True)
class StoredMessage:
    message_id: str
    sequence_number: int
    body_hash: bytes

class MessageStore:
    """Process-local replay and duplicate index for development.

    State is intentionally not durable and is lost when the gateway restarts. A production
    adapter must perform these checks atomically in the external durable backend.
    """

    def __init__(self, replay_window_size: int = 1024) -> None:
        self.replay_window_size = replay_window_size
        self._by_message: dict[tuple[str, str], StoredMessage] = {}
        self._by_sequence: dict[tuple[str, int], StoredMessage] = {}
        self._highest: dict[str, int] = {}
        self._lock = threading.Lock()

    def store(
        self, device_id: str, message_id: str, sequence_number: int,
        kind: str, body_hash: bytes, body: bytes,
    ) -> StoreResult:
        del kind
        del body  # The development index stores metadata only.

        with self._lock:
            by_id = self._by_message.get((device_id, message_id))

            if by_id is not None:
                exact = by_id.sequence_number == sequence_number and by_id.body_hash == body_hash
                return StoreResult("duplicate" if exact else "conflict")

            if (device_id, sequence_number) in self._by_sequence:
                return StoreResult("conflict")

            highest = self._highest.get(device_id)

            if highest is not None and sequence_number <= highest - self.replay_window_size:
                return StoreResult("replay")

            stored = StoredMessage(message_id, sequence_number, body_hash)
            self._by_message[(device_id, message_id)] = stored
            self._by_sequence[(device_id, sequence_number)] = stored
            if highest is None or sequence_number > highest:
                self._highest[device_id] = sequence_number
            else:
                self._highest[device_id] = highest
            self._prune(device_id)

            return StoreResult("accepted")

    def _prune(self, device_id: str) -> None:
        cutoff = self._highest[device_id] - self.replay_window_size
        expired = [key for key in self._by_sequence if key[0] == device_id and key[1] <= cutoff]

        for key in expired:
            stored = self._by_sequence.pop(key)
            self._by_message.pop((device_id, stored.message_id), None)

    def close(self) -> None:
        """Retained as a no-op so server lifecycle code is adapter-independent."""

