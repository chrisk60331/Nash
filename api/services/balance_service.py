from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from api.config import settings
from api.monetization_models import BalanceRecord, LedgerEntry
from api.services.async_runner import run_async
from api.services.backboard_service import get_client
from api.services.user_service import get_user_config_assistant_id_async

BALANCE_META_TYPE = "nash_balance"
LEDGER_META_TYPE = "nash_balance_ledger"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def usd_to_token_credits(usd_value: float) -> int:
    return max(0, int(round(usd_value * settings.token_credits_per_usd)))


def token_credits_to_usd(token_credits: int) -> float:
    if settings.token_credits_per_usd <= 0:
        return 0.0
    return round(token_credits / settings.token_credits_per_usd, 2)


def _extract_balance_bundle_from_memories(
    memories,
) -> tuple[BalanceRecord | None, list[LedgerEntry]]:
    balance_record: BalanceRecord | None = None
    ledger_records: list[LedgerEntry] = []

    for memory in memories or []:
        meta = getattr(memory, "metadata", None) or {}
        memory_type = meta.get("type")
        try:
            parsed = json.loads(memory.content)
        except (TypeError, json.JSONDecodeError):
            continue

        if memory_type == BALANCE_META_TYPE:
            try:
                balance_record = BalanceRecord.model_validate(parsed)
            except Exception:
                continue
        elif memory_type == LEDGER_META_TYPE:
            try:
                ledger_records.append(LedgerEntry.model_validate(parsed))
            except Exception:
                continue

    ledger_records.sort(key=lambda item: item.createdAt, reverse=True)
    return balance_record, ledger_records


async def _load_balance_bundle(
    user_id: str,
) -> tuple[tuple[BalanceRecord, str] | None, list[tuple[LedgerEntry, str]]]:
    assistant_id = await get_user_config_assistant_id_async(user_id)
    client = get_client()
    response = await client.get_memories(assistant_id)

    balance_record, ledger_records = _extract_balance_bundle_from_memories(response.memories)
    balance_row: tuple[BalanceRecord, str] | None = None
    ledger_rows: list[tuple[LedgerEntry, str]] = []

    if balance_record is not None:
        balance_row = (balance_record, "")
        for memory in response.memories:
            meta = memory.metadata or {}
            if meta.get("type") == BALANCE_META_TYPE:
                balance_row = (balance_record, memory.id)
                break

    if ledger_records:
        ledger_rows = [(record, "") for record in ledger_records]
        for memory in response.memories:
            meta = memory.metadata or {}
            if meta.get("type") != LEDGER_META_TYPE:
                continue
            try:
                parsed = json.loads(memory.content)
                record = LedgerEntry.model_validate(parsed)
            except Exception:
                continue
            for idx, (existing, _) in enumerate(ledger_rows):
                if existing.id == record.id:
                    ledger_rows[idx] = (record, memory.id)
                    break

    return balance_row, ledger_rows


async def _persist_balance(user_id: str, record: BalanceRecord, memory_id: str | None = None) -> BalanceRecord:
    assistant_id = await get_user_config_assistant_id_async(user_id)
    client = get_client()
    payload = record.model_dump(mode="json")
    metadata = {"type": BALANCE_META_TYPE, "user": user_id}
    if memory_id:
        await client.update_memory(
            assistant_id=assistant_id,
            memory_id=memory_id,
            content=json.dumps(payload),
            metadata=metadata,
        )
    else:
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(payload),
            metadata=metadata,
        )
    return record


def get_or_create_balance_record(user_id: str) -> BalanceRecord:
    balance_row, _ = run_async(_load_balance_bundle(user_id))
    if balance_row:
        return balance_row[0]

    record = BalanceRecord(user=user_id)
    run_async(_persist_balance(user_id, record))
    return record


def get_balance_response(user_id: str) -> dict:
    record = get_or_create_balance_record(user_id)
    payload = record.model_dump(mode="json")
    payload["tokenCreditsUsd"] = token_credits_to_usd(record.tokenCredits)
    return payload


def get_balance_response_from_memories(memories, user_id: str) -> dict:
    balance_record, _ = _extract_balance_bundle_from_memories(memories)
    if not balance_record:
        balance_record = BalanceRecord(user=user_id)
        run_async(_persist_balance(user_id, balance_record))
    payload = balance_record.model_dump(mode="json")
    payload["tokenCreditsUsd"] = token_credits_to_usd(balance_record.tokenCredits)
    return payload


def list_ledger_entries(user_id: str, limit: int = 20) -> list[dict]:
    _, ledger_rows = run_async(_load_balance_bundle(user_id))
    entries = [entry.model_dump(mode="json") for entry, _ in ledger_rows[:limit]]
    for entry in entries:
        entry["tokenCreditsUsd"] = token_credits_to_usd(int(entry["tokenCreditsDelta"]))
    return entries


def award_token_credits(
    user_id: str,
    *,
    token_credits: int,
    entry_type: str,
    description: str,
    metadata: dict[str, str | int | float | bool | None] | None = None,
) -> dict:
    if token_credits <= 0:
        return get_balance_response(user_id)

    balance_row, _ = run_async(_load_balance_bundle(user_id))
    if balance_row:
        balance_record, balance_memory_id = balance_row
    else:
        balance_record = BalanceRecord(user=user_id)
        balance_memory_id = None

    updated_balance = balance_record.model_copy(
        update={"tokenCredits": balance_record.tokenCredits + token_credits}
    )
    run_async(_persist_balance(user_id, updated_balance, balance_memory_id))

    now = _now()
    entry = LedgerEntry(
        id=str(uuid.uuid4()),
        user=user_id,
        entryType=entry_type,
        tokenCreditsDelta=token_credits,
        usdValue=token_credits_to_usd(token_credits),
        description=description,
        metadata=metadata or {},
        createdAt=now,
        updatedAt=now,
    )

    async def _create_entry() -> None:
        assistant_id = await get_user_config_assistant_id_async(user_id)
        client = get_client()
        await client.add_memory(
            assistant_id=assistant_id,
            content=json.dumps(entry.model_dump(mode="json")),
            metadata={
                "type": LEDGER_META_TYPE,
                "user": user_id,
                "entryType": entry.entryType,
                "entryId": entry.id,
            },
        )

    run_async(_create_entry())
    return get_balance_response(user_id)
