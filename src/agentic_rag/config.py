"""Configuration loaded from environment variables.

The service is intentionally env-driven: Docker, CI, and local runs all use the
same settings object, and tests can construct one without touching the process
environment.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_LLM_BASE_URL = "https://api.siliconflow.cn/v1"
DEFAULT_LLM_MODEL = "Qwen/Qwen3-8B"
DEFAULT_EMB_MODEL = "BAAI/bge-m3"


def load_dotenv(path: Path) -> int:
    """Minimal .env loader: real environment variables always win."""
    if not path.exists():
        return 0
    loaded = 0
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.split(" #", 1)[0].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        if key and key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_api_key: str = ""
    llm_model: str = DEFAULT_LLM_MODEL
    emb_model: str = DEFAULT_EMB_MODEL
    disable_thinking: bool = True
    data_dir: Path = field(default_factory=lambda: Path("data"))
    runs_dir: Path = field(default_factory=lambda: Path("runs"))
    api_keys: tuple[str, ...] = ()
    rate_limit_per_minute: int = 60
    max_steps: int = 6
    request_timeout_s: float = 60.0
    environment: str = "dev"
    log_level: str = "INFO"
    docs_enabled: bool = True
    allow_anonymous: bool = False

    @classmethod
    def from_env(cls, *, env_file: str | Path | None = ".env") -> Settings:
        if env_file:
            load_dotenv(Path(env_file))
        keys = tuple(
            k.strip()
            for k in os.environ.get("API_KEYS", "").split(",")
            if k.strip()
        )
        data_dir = Path(os.environ.get("AGENTIC_RAG_DATA_DIR", "data")).expanduser()
        runs_dir = Path(os.environ.get("RUNS_DIR", "runs")).expanduser()
        return cls(
            llm_base_url=os.environ.get("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/"),
            llm_api_key=os.environ.get("LLM_API_KEY", ""),
            llm_model=os.environ.get("LLM_MODEL", DEFAULT_LLM_MODEL),
            emb_model=os.environ.get("EMB_MODEL", DEFAULT_EMB_MODEL),
            disable_thinking=_bool("DISABLE_THINKING", True),
            data_dir=data_dir,
            runs_dir=runs_dir,
            api_keys=keys,
            rate_limit_per_minute=max(1, int(os.environ.get("RATE_LIMIT_PER_MINUTE", "60"))),
            max_steps=max(1, min(12, int(os.environ.get("MAX_STEPS", "6")))),
            request_timeout_s=float(os.environ.get("REQUEST_TIMEOUT_S", "60")),
            environment=os.environ.get("ENVIRONMENT", "dev"),
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            docs_enabled=_bool("DOCS_ENABLED", True),
            allow_anonymous=_bool("ALLOW_ANONYMOUS", False),
        )

    @property
    def kb_dir(self) -> Path:
        return self.data_dir / "kb"

    def kb_ids(self) -> list[str]:
        if not self.kb_dir.exists():
            return []
        return sorted(
            p.name for p in self.kb_dir.iterdir()
            if p.is_dir() and (p / "index" / "meta.json").exists()
        )

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.data_dir.exists():
            problems.append(f"data directory does not exist: {self.data_dir}")
        if not self.kb_ids():
            problems.append(f"no indexed knowledge bases under: {self.kb_dir}")
        return problems

    def public_dict(self) -> dict:
        return {
            "llm_model": self.llm_model,
            "emb_model": self.emb_model,
            "environment": self.environment,
            "data_dir": str(self.data_dir),
            "kbs": self.kb_ids(),
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "max_steps": self.max_steps,
        }
