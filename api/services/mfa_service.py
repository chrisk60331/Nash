from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Literal
from urllib.parse import quote

import pyotp
from pydantic import BaseModel, Field
from werkzeug.security import check_password_hash, generate_password_hash


class BackupCodeRecord(BaseModel):
    codeHash: str
    used: bool = False
    usedAt: str | None = None


class BackupCodeValidationResult(BaseModel):
    valid: bool
    matchedIndex: int | None = None
    records: list[BackupCodeRecord] = Field(default_factory=list)


def generate_totp_secret() -> str:
    return pyotp.random_base32()


def build_otpauth_url(*, secret: str, issuer: str, account_name: str) -> str:
    encoded_label = quote(f"{issuer}:{account_name}")
    encoded_issuer = quote(issuer)
    return (
        f"otpauth://totp/{encoded_label}"
        f"?secret={secret}&issuer={encoded_issuer}&algorithm=SHA1&digits=6&period=30"
    )


def verify_totp(secret: str, token: str) -> bool:
    if not secret or not token:
        return False
    return pyotp.TOTP(secret).verify(token, valid_window=1)


def generate_backup_codes(*, count: int = 8, length: int = 8) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return ["".join(secrets.choice(alphabet) for _ in range(length)) for _ in range(count)]


def hash_backup_codes(codes: list[str]) -> list[BackupCodeRecord]:
    return [BackupCodeRecord(codeHash=generate_password_hash(code)) for code in codes]


def validate_backup_code(records: list[dict] | list[BackupCodeRecord], candidate: str) -> BackupCodeValidationResult:
    parsed_records = [
        record if isinstance(record, BackupCodeRecord) else BackupCodeRecord.model_validate(record)
        for record in records
    ]
    normalized_candidate = candidate.strip().upper()

    for index, record in enumerate(parsed_records):
        if record.used:
            continue
        if check_password_hash(record.codeHash, normalized_candidate):
            updated_records = list(parsed_records)
            updated_records[index] = record.model_copy(
                update={
                    "used": True,
                    "usedAt": datetime.now(timezone.utc).isoformat(),
                }
            )
            return BackupCodeValidationResult(valid=True, matchedIndex=index, records=updated_records)

    return BackupCodeValidationResult(valid=False, records=parsed_records)


def mfa_requirement_for_user(role: str, require_for_all_users: bool) -> Literal["optional", "required"]:
    if role.upper() == "ADMIN" or require_for_all_users:
        return "required"
    return "optional"
