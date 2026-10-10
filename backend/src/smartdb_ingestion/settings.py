from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix = "SMARTDB_", env_file = ".env", extra = "ignore")

    host: str = "127.0.0.1"
    port: int = Field(default = 5687, ge = 1, le = 65535)
    transport_mode: Literal["secure", "insecure-dev"] = "secure"
    max_payload_bytes: int = Field(default = 1024, ge = 64, le = 65536)
    rate_limit_per_minute: int = Field(default = 120, ge = 1)
    replay_window_size: int = Field(default = 1024, ge = 64, le = 65536)
    config_path: Path = Path("./config/device-config.cbor")
    config_key_id: str = "development-unsigned"
    dtls_psk_file: Path | None = None

    @model_validator(mode="after")
    def secure_mode_requires_credentials(self) -> "Settings":
        if self.transport_mode == "secure" and self.dtls_psk_file is None:
            raise ValueError("secure mode requires SMARTDB_DTLS_PSK_FILE")
        return self
