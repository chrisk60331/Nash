from __future__ import annotations

import json
from datetime import datetime, timezone

from pydantic import BaseModel

from api.config import settings
from api.services.async_runner import run_async
from api.services.backboard_service import get_client

ORG_SECURITY_META_TYPE = "org_security_config"


class OrgSecurityConfig(BaseModel):
    requireMfaForAllUsers: bool = False


async def _find_org_security_memory() -> tuple[OrgSecurityConfig, str | None]:
    client = get_client()
    response = await client.get_memories(settings.backboard_auth_assistant_id)
    for memory in response.memories:
        meta = memory.metadata or {}
        if meta.get("type") != ORG_SECURITY_META_TYPE:
            continue
        try:
            return OrgSecurityConfig.model_validate(json.loads(memory.content or "{}")), memory.id
        except Exception:
            return OrgSecurityConfig(), memory.id
    return OrgSecurityConfig(), None


def get_org_security_config() -> OrgSecurityConfig:
    config, _memory_id = run_async(_find_org_security_memory())
    return config


def update_org_security_config(*, require_mfa_for_all_users: bool) -> OrgSecurityConfig:
    config, memory_id = run_async(_find_org_security_memory())
    updated = config.model_copy(update={"requireMfaForAllUsers": require_mfa_for_all_users})
    payload = updated.model_dump(mode="json")

    async def _save() -> None:
        client = get_client()
        metadata = {
            "type": ORG_SECURITY_META_TYPE,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        }
        if memory_id:
            await client.update_memory(
                assistant_id=settings.backboard_auth_assistant_id,
                memory_id=memory_id,
                content=json.dumps(payload),
                metadata=metadata,
            )
        else:
            await client.add_memory(
                assistant_id=settings.backboard_auth_assistant_id,
                content=json.dumps(payload),
                metadata=metadata,
            )

    run_async(_save())
    return updated
