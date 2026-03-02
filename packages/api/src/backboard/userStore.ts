import { logger } from '@librechat/data-schemas';
import { backboardStorage } from './storage';

import type { BackboardMemory } from './types';

const CONVO_TYPE = 'librechat_convo';
const MSG_TYPE = 'librechat_msg';

interface CachedEntry {
  bbId: string;
  data: Record<string, unknown>;
}

interface UserCache {
  convos: Map<string, CachedEntry>;
  msgs: Map<string, CachedEntry>;
  loaded: boolean;
}

const userAssistantIds = new Map<string, string>();
const userCaches = new Map<string, UserCache>();

function getClient() {
  return backboardStorage.getClient();
}

export async function getUserAssistantId(userId: string): Promise<string> {
  const cached = userAssistantIds.get(userId);
  if (cached) {
    return cached;
  }

  const bb = getClient();
  const name = `librechat-user-${userId}`;
  const assistants = await bb.listAssistants();
  const existing = assistants.find((a) => a.name === name);

  if (existing) {
    userAssistantIds.set(userId, existing.assistant_id);
    return existing.assistant_id;
  }

  const created = await bb.createAssistant(name, `LibreChat data store for user ${userId}`);
  userAssistantIds.set(userId, created.assistant_id);
  logger.info(`[UserStore] Created per-user assistant ${created.assistant_id} for ${userId}`);
  return created.assistant_id;
}

function emptyCache(): UserCache {
  return { convos: new Map(), msgs: new Map(), loaded: false };
}

export async function getUserCache(userId: string): Promise<UserCache> {
  const existing = userCaches.get(userId);
  if (existing?.loaded) {
    return existing;
  }

  const cache = emptyCache();
  const bb = getClient();
  const aid = await getUserAssistantId(userId);
  const response = await bb.getMemories(aid);

  for (const m of response.memories) {
    const meta = (m.metadata ?? {}) as Record<string, unknown>;
    const type = meta.type as string;

    if (type === CONVO_TYPE) {
      try {
        const data = JSON.parse(m.content) as Record<string, unknown>;
        const cid = (meta.conversationId ?? data.conversationId) as string;
        if (cid) {
          cache.convos.set(cid, { bbId: m.id, data });
        }
      } catch { /* skip malformed */ }
    } else if (type === MSG_TYPE) {
      try {
        const data = JSON.parse(m.content) as Record<string, unknown>;
        const mid = (meta.messageId ?? data.messageId) as string;
        if (mid) {
          cache.msgs.set(mid, { bbId: m.id, data });
        }
      } catch { /* skip malformed */ }
    }
  }

  cache.loaded = true;
  userCaches.set(userId, cache);
  return cache;
}

export function invalidateUserCache(userId: string): void {
  userCaches.delete(userId);
}

export async function upsertConvo(
  userId: string,
  conversationId: string,
  data: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const cache = await getUserCache(userId);
  const existing = cache.convos.get(conversationId);
  const bb = getClient();
  const aid = await getUserAssistantId(userId);

  if (existing) {
    await bb.deleteMemory(aid, existing.bbId);
  }

  const merged = existing ? { ...existing.data, ...data } : data;
  merged.conversationId = conversationId;
  merged.user = userId;

  const content = JSON.stringify(merged);
  const result = await bb.addMemory(aid, content, {
    type: CONVO_TYPE,
    conversationId,
    user: userId,
    updatedAt: new Date().toISOString(),
  });

  const bbId = (result.memory_id ?? result.id ?? '') as string;
  cache.convos.set(conversationId, { bbId, data: merged });
  return merged;
}

export async function deleteConvo(userId: string, conversationId: string): Promise<boolean> {
  const cache = await getUserCache(userId);
  const entry = cache.convos.get(conversationId);
  if (!entry) {
    return false;
  }

  const bb = getClient();
  const aid = await getUserAssistantId(userId);
  await bb.deleteMemory(aid, entry.bbId);
  cache.convos.delete(conversationId);
  return true;
}

export async function upsertMessage(
  userId: string,
  messageId: string,
  data: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const cache = await getUserCache(userId);
  const existing = cache.msgs.get(messageId);
  const bb = getClient();
  const aid = await getUserAssistantId(userId);

  if (existing) {
    await bb.deleteMemory(aid, existing.bbId);
  }

  const merged = existing ? { ...existing.data, ...data } : data;
  merged.messageId = messageId;
  merged.user = userId;

  if (!merged.createdAt) {
    merged.createdAt = new Date().toISOString();
  }
  merged.updatedAt = new Date().toISOString();

  const content = JSON.stringify(merged);
  const result = await bb.addMemory(aid, content, {
    type: MSG_TYPE,
    messageId,
    conversationId: (merged.conversationId ?? '') as string,
    user: userId,
    createdAt: merged.createdAt as string,
  });

  const bbId = (result.memory_id ?? result.id ?? '') as string;
  cache.msgs.set(messageId, { bbId, data: merged });
  return merged;
}

export async function deleteMsg(userId: string, messageId: string): Promise<boolean> {
  const cache = await getUserCache(userId);
  const entry = cache.msgs.get(messageId);
  if (!entry) {
    return false;
  }

  const bb = getClient();
  const aid = await getUserAssistantId(userId);
  await bb.deleteMemory(aid, entry.bbId);
  cache.msgs.delete(messageId);
  return true;
}

export async function getConvoFromCache(
  userId: string,
  conversationId: string,
): Promise<Record<string, unknown> | null> {
  const cache = await getUserCache(userId);
  return cache.convos.get(conversationId)?.data ?? null;
}

export async function getAllConvos(userId: string): Promise<Record<string, unknown>[]> {
  const cache = await getUserCache(userId);
  return Array.from(cache.convos.values()).map((e) => e.data);
}

export async function getMsgFromCache(
  userId: string,
  messageId: string,
): Promise<Record<string, unknown> | null> {
  const cache = await getUserCache(userId);
  return cache.msgs.get(messageId)?.data ?? null;
}

export async function getMsgsByConvo(
  userId: string,
  conversationId: string,
): Promise<Record<string, unknown>[]> {
  const cache = await getUserCache(userId);
  const results: Record<string, unknown>[] = [];
  for (const entry of cache.msgs.values()) {
    if (entry.data.conversationId === conversationId) {
      results.push(entry.data);
    }
  }
  results.sort((a, b) => {
    const ta = new Date(a.createdAt as string).getTime();
    const tb = new Date(b.createdAt as string).getTime();
    return ta - tb;
  });
  return results;
}

/** Scans all loaded user caches to find which user owns a conversation. */
export async function findUserForConvo(conversationId: string): Promise<string | undefined> {
  for (const [userId, cache] of userCaches.entries()) {
    if (cache.convos.has(conversationId)) {
      return userId;
    }
  }
  return undefined;
}

export async function deleteMsgsByConvo(userId: string, conversationId: string): Promise<number> {
  const cache = await getUserCache(userId);
  const bb = getClient();
  const aid = await getUserAssistantId(userId);
  let count = 0;

  const toDelete: string[] = [];
  for (const [mid, entry] of cache.msgs.entries()) {
    if (entry.data.conversationId === conversationId) {
      toDelete.push(mid);
    }
  }

  for (const mid of toDelete) {
    const entry = cache.msgs.get(mid);
    if (entry) {
      await bb.deleteMemory(aid, entry.bbId);
      cache.msgs.delete(mid);
      count++;
    }
  }

  return count;
}
