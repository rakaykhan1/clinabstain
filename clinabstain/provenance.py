"""Run provenance: what exactly was run, when, and how.

Every summary file gets a `provenance` block so that a result can be traced to an exact model snapshot,
prompt, scorer version and date. Reviewers of health benchmarks (for example the HCMetaBench rubric) cap
any study that does not report exact model identity, so this is recorded automatically rather than by hand.
"""
from __future__ import annotations

import hashlib
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from .core import CLOSED_BOOK_PROMPT, SYSTEM_PROMPT

ROOT = Path(__file__).resolve().parent.parent

# Model identifiers returned by the API in each reply (the `model` field). Filled in by models.py as calls are made.
SERVED_MODELS: set[str] = set()


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _git_commit() -> str | None:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=5)
        dirty = subprocess.run(["git", "status", "--porcelain", "--", "clinabstain", "data", "run.py", "run_local.py"],
                               cwd=ROOT, capture_output=True, text=True, timeout=5)
        if out.returncode != 0:
            return None
        return out.stdout.strip() + ("-dirty" if dirty.stdout.strip() else "")
    except Exception:  # noqa: BLE001  git not installed or not a checkout
        return None


def _version() -> str | None:
    try:
        for line in (ROOT / "pyproject.toml").read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("version"):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        return None
    return None


def prompt_sha256() -> str:
    return hashlib.sha256((SYSTEM_PROMPT + "\n---\n" + CLOSED_BOOK_PROMPT).encode("utf-8")).hexdigest()[:16]


def block(spec: str, started: str, **extra) -> dict:
    temp = os.environ.get("CLINABSTAIN_TEMPERATURE", "")
    kind = spec.partition(":")[0]
    return {
        "model_spec": spec,
        "served_models": sorted(SERVED_MODELS) or None,
        "started_utc": started,
        "finished_utc": now_utc(),
        "temperature": "provider default" if temp.lower() == "default" else 0.0,
        "api_version": os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21") if kind == "azure" else None,
        "base_url": os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1") if kind == "openai" else None,
        "clinabstain_version": _version(),
        "git_commit": _git_commit(),
        "prompt_sha256": prompt_sha256(),
        "passage_shuffle_seed": os.environ.get("CLINABSTAIN_SHUFFLE_SEED") or None,
        "python": platform.python_version(),
        **extra,
    }
