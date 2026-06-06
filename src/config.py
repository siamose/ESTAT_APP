from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


def load_dotenv(path: Path | None = None) -> None:
    """Load simple KEY=VALUE pairs without requiring python-dotenv."""
    env_path = path or APP_ROOT / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class AppConfig:
    estat_api_key: str | None
    streamlit_server_port: str | None

    @property
    def has_api_key(self) -> bool:
        return bool(self.estat_api_key)


def _get_estat_api_key() -> str | None:
    """st.secrets → 環境変数 の順で API キーを取得する。"""
    try:
        import streamlit as st
        value = st.secrets.get("ESTAT_API_KEY") or st.secrets.get("eSTAT_API_KEY")
        if value:
            return str(value)
    except Exception:
        pass
    return os.getenv("ESTAT_API_KEY") or os.getenv("eSTAT_API_KEY")


def get_config() -> AppConfig:
    load_dotenv()
    return AppConfig(
        estat_api_key=_get_estat_api_key(),
        streamlit_server_port=os.getenv("STREAMLIT_SERVER_PORT"),
    )


def require_api_key() -> str:
    config = get_config()
    if not config.estat_api_key:
        raise EnvironmentError(
            "eSTAT_API_KEY が設定されていません。.env またはOS環境変数に設定してください。"
        )
    return config.estat_api_key
