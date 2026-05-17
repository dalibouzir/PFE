from __future__ import annotations

import os
import uuid
from pathlib import Path

import httpx
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.uploaded_file import UploadedFile
from app.services.helpers import get_manager_cooperative_id
from app.utils.exceptions import ValidationError

ALLOWED_UPLOAD_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
}
ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".webp"}


def _uploads_root() -> Path:
    root = Path(settings.uploads_dir)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _sanitize_name(filename: str) -> str:
    base = os.path.basename(filename or "file")
    return "".join(ch for ch in base if ch.isalnum() or ch in {".", "-", "_"}) or "file"


def _supabase_storage_enabled() -> bool:
    url = (settings.supabase_url or "").strip()
    key = (settings.supabase_service_role_key or "").strip()
    if not url or not key:
        return False
    if "your-project-id" in url or "your-supabase-service-role-key" in key:
        return False
    return True


def _upload_to_supabase(relative_path: str, payload: bytes, content_type: str) -> str:
    base = settings.supabase_url.rstrip("/")
    bucket = (settings.supabase_uploads_bucket or "weefarm-uploads").strip()
    object_path = f"{bucket}/{relative_path}"
    upload_url = f"{base}/storage/v1/object/{object_path}"
    headers = {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    with httpx.Client(timeout=30.0) as client:
        response = client.post(upload_url, headers=headers, content=payload)
    if response.status_code >= 400:
        raise ValidationError("Upload Supabase échoué. Vérifiez la configuration storage.")
    return f"{base}/storage/v1/object/public/{object_path}"


def _save_entity_file(
    db: Session,
    manager,
    *,
    entity_id,
    file: UploadFile,
    entity_type: str,
    folder: str,
    fallback_name: str,
) -> UploadedFile:
    cooperative_id = get_manager_cooperative_id(manager)

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise ValidationError("Format non supporté. Autorisés: PDF, JPG, JPEG, PNG, WEBP.")

    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_UPLOAD_MIME_TYPES:
        raise ValidationError("Type MIME non supporté pour justificatif.")

    payload = file.file.read()
    size_bytes = len(payload)
    if size_bytes <= 0:
        raise ValidationError("Fichier vide.")
    if size_bytes > 10 * 1024 * 1024:
        raise ValidationError("Fichier trop volumineux (max 10MB).")

    filename = _sanitize_name(file.filename or f"{fallback_name}{suffix}")
    generated = f"{uuid.uuid4().hex}{suffix}"
    relative_dir = Path(folder) / str(cooperative_id) / str(entity_id)
    relative_path = str((relative_dir / generated).as_posix())
    if _supabase_storage_enabled():
        file_url = _upload_to_supabase(relative_path, payload, content_type)
    else:
        root = _uploads_root()
        abs_dir = root / relative_dir
        abs_dir.mkdir(parents=True, exist_ok=True)
        abs_path = abs_dir / generated
        abs_path.write_bytes(payload)
        file_url = f"/uploads/{relative_path}"

    uploaded = UploadedFile(
        cooperative_id=cooperative_id,
        entity_type=entity_type,
        entity_id=entity_id,
        filename=filename,
        mime_type=content_type,
        size_bytes=size_bytes,
        storage_path=relative_path,
        file_url=file_url,
    )
    db.add(uploaded)
    db.flush()
    return uploaded


def save_collecte_justificatif(
    db: Session,
    manager,
    *,
    entity_id,
    file: UploadFile,
) -> UploadedFile:
    return _save_entity_file(
        db,
        manager,
        entity_id=entity_id,
        file=file,
        entity_type="collecte_input",
        folder="collecte",
        fallback_name="collecte",
    )


def save_farmer_advance_devis(
    db: Session,
    manager,
    *,
    entity_id,
    file: UploadFile,
) -> UploadedFile:
    return _save_entity_file(
        db,
        manager,
        entity_id=entity_id,
        file=file,
        entity_type="farmer_advance",
        folder="farmer-advances",
        fallback_name="devis",
    )


def save_treasury_justificatif(
    db: Session,
    manager,
    *,
    entity_id,
    file: UploadFile,
) -> UploadedFile:
    return _save_entity_file(
        db,
        manager,
        entity_id=entity_id,
        file=file,
        entity_type="treasury_transaction",
        folder="treasury",
        fallback_name="justificatif",
    )
