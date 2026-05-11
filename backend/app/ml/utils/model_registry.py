from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings

MODEL_REGISTRY_FILE = "model_registry.json"
ACTIVE_MODEL_FILE = "active_model.json"
VERSION_DIR_NAME = "versions"


class RegistryError(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifacts_dir() -> Path:
    path = Path(settings.ml_artifacts_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _registry_path() -> Path:
    return _artifacts_dir() / MODEL_REGISTRY_FILE


def _active_path() -> Path:
    return _artifacts_dir() / ACTIVE_MODEL_FILE


def _version_dir(model_version: str) -> Path:
    path = _artifacts_dir() / VERSION_DIR_NAME / model_version
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path, default: Dict) -> Dict:
    if not path.exists():
        return dict(default)
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return dict(default)


def _write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _git_sha() -> Optional[str]:
    try:
        output = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return None
    return output or None


def _default_registry() -> Dict:
    return {
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "versions": [],
    }


def _default_active() -> Dict:
    return {
        "active_model_version": None,
        "previous_model_version": None,
        "updated_at": _utc_now(),
    }


def _load_registry() -> Dict:
    registry = _read_json(_registry_path(), _default_registry())
    registry.setdefault("versions", [])
    registry.setdefault("updated_at", _utc_now())
    return registry


def _save_registry(registry: Dict) -> None:
    registry["updated_at"] = _utc_now()
    _write_json(_registry_path(), registry)


def get_registry_versions() -> List[Dict]:
    return list(_load_registry().get("versions", []))


def get_active_model_version() -> Optional[Dict]:
    active = _read_json(_active_path(), _default_active())
    active_version = active.get("active_model_version")
    if not active_version:
        return None
    for version in get_registry_versions():
        if version.get("model_version") == active_version:
            return version
    return None


def materialize_model_artifacts(model_version: str) -> Dict[str, str]:
    source_dir = _artifacts_dir() / VERSION_DIR_NAME / model_version
    if not source_dir.exists():
        raise RegistryError(f"Missing versioned artifacts for model_version={model_version}")

    copied: Dict[str, str] = {}
    for item in source_dir.iterdir():
        if item.is_file() and item.suffix in {".joblib", ".json"}:
            destination = _artifacts_dir() / item.name
            shutil.copy2(item, destination)
            copied[item.name] = str(destination)
    return copied


def register_model_version(
    *,
    model_version: str,
    run_name: str,
    feature_schema_version: str,
    training_rows: int,
    metrics: Dict,
    artifact_paths: Dict[str, str],
    status: str = "candidate",
    notes: str = "",
    validation: Optional[Dict] = None,
    extra_metadata: Optional[Dict] = None,
) -> Dict:
    registry = _load_registry()
    versions: List[Dict] = registry.get("versions", [])

    existing = next((item for item in versions if item.get("model_version") == model_version), None)
    record = {
        "model_version": model_version,
        "trained_at": _utc_now(),
        "run_name": run_name,
        "feature_schema_version": feature_schema_version,
        "training_rows": int(training_rows),
        "metrics": metrics,
        "artifact_paths": artifact_paths,
        "git_sha": _git_sha(),
        "status": status,
        "notes": notes,
        "validation": validation or {},
        "updated_at": _utc_now(),
        "mvp_demo_allowed": bool((validation or {}).get("mvp_demo_allowed", False)),
        "production_ready": bool((validation or {}).get("production_ready", False)),
    }
    if extra_metadata:
        record.update(extra_metadata)

    if existing:
        versions[versions.index(existing)] = {**existing, **record}
    else:
        versions.append(record)

    registry["versions"] = versions
    _save_registry(registry)
    return record


def set_active_model_version(model_version: str, notes: str = "") -> Dict:
    registry = _load_registry()
    versions: List[Dict] = registry.get("versions", [])
    target = next((item for item in versions if item.get("model_version") == model_version), None)
    if not target:
        raise RegistryError(f"Unknown model_version={model_version}")

    active_state = _read_json(_active_path(), _default_active())
    current_active = active_state.get("active_model_version")

    previous_active = current_active if current_active and current_active != model_version else active_state.get("previous_model_version")

    materialize_model_artifacts(model_version)

    for version in versions:
        if version.get("model_version") == model_version:
            version["status"] = "active"
            if notes:
                version["notes"] = notes
            version["updated_at"] = _utc_now()
        elif version.get("model_version") == current_active:
            version["status"] = "archived"
            version["updated_at"] = _utc_now()

    registry["versions"] = versions
    _save_registry(registry)

    _write_json(
        _active_path(),
        {
            "active_model_version": model_version,
            "previous_model_version": previous_active,
            "updated_at": _utc_now(),
        },
    )
    return next(item for item in versions if item.get("model_version") == model_version)


def rollback_active_model() -> Dict:
    active_state = _read_json(_active_path(), _default_active())
    previous_model_version = active_state.get("previous_model_version")
    if not previous_model_version:
        raise RegistryError("No previous active model is available for rollback.")
    return set_active_model_version(previous_model_version, notes="Rollback activated")


def store_versioned_artifacts(model_version: str, artifact_paths: Dict[str, str]) -> Dict[str, str]:
    version_dir = _version_dir(model_version)
    stored: Dict[str, str] = {}
    for key, path_value in artifact_paths.items():
        source = Path(path_value)
        if not source.exists():
            continue
        target = version_dir / source.name
        shutil.copy2(source, target)
        stored[key] = str(target)
    return stored


def ensure_registry_files() -> None:
    if not _registry_path().exists():
        _write_json(_registry_path(), _default_registry())
    if not _active_path().exists():
        _write_json(_active_path(), _default_active())
