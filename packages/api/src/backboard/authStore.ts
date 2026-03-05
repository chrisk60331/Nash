import { logger } from '@librechat/data-schemas';
import { backboardStorage } from './storage';

const AUTH_USER = 'librechat_user';
const AUTH_SESSION = 'librechat_session';
const AUTH_TOKEN = 'librechat_token';

type AuthEntryType = typeof AUTH_USER | typeof AUTH_SESSION | typeof AUTH_TOKEN;

interface CachedEntry {
  bbId: string;
  data: Record<string, unknown>;
}

interface AuthCache {
  users: Map<string, CachedEntry>;
  usersByEmail: Map<string, string>;
  sessions: Map<string, CachedEntry>;
  tokens: Map<string, CachedEntry>;
  loaded: boolean;
}

let authAssistantId: string | null = null;
let authCache: AuthCache | null = null;

function getClient() {
  return backboardStorage.getClient();
}

async function getAuthAssistantId(): Promise<string> {
  if (authAssistantId) {
    return authAssistantId;
  }

  const envId = process.env.BACKBOARD_AUTH_ASSISTANT_ID;
  if (envId) {
    authAssistantId = envId;
    logger.info(`[AuthStore] Using auth assistant from env: ${authAssistantId}`);
    return authAssistantId;
  }

  const bb = getClient();
  const assistants = await bb.listAssistants();
  const existing = assistants.find((a) => a.name === 'librechat-auth');

  if (existing) {
    authAssistantId = existing.assistant_id;
    logger.info(`[AuthStore] Found auth assistant by name: ${authAssistantId}`);
    return authAssistantId;
  }

  const created = await bb.createAssistant(
    'librechat-auth',
    'LibreChat authentication store powered by Backboard',
  );
  authAssistantId = created.assistant_id;
  logger.info(`[AuthStore] Created auth assistant: ${authAssistantId}`);
  return authAssistantId;
}

function getMapForType(cache: AuthCache, type: AuthEntryType): Map<string, CachedEntry> {
  if (type === AUTH_USER) {
    return cache.users;
  }
  if (type === AUTH_SESSION) {
    return cache.sessions;
  }
  return cache.tokens;
}

async function getAuthCache(): Promise<AuthCache> {
  if (authCache?.loaded) {
    return authCache;
  }

  const cache: AuthCache = {
    users: new Map(),
    usersByEmail: new Map(),
    sessions: new Map(),
    tokens: new Map(),
    loaded: false,
  };

  const bb = getClient();
  const aid = await getAuthAssistantId();
  const response = await bb.getMemories(aid);

  for (const m of response.memories) {
    const meta = (m.metadata ?? {}) as Record<string, unknown>;
    const type = meta.type as string;

    if (type !== AUTH_USER && type !== AUTH_SESSION && type !== AUTH_TOKEN) {
      continue;
    }

    try {
      const data = JSON.parse(m.content) as Record<string, unknown>;
      const entryId = (meta.entryId ?? data._id) as string;
      if (!entryId) {
        continue;
      }

      getMapForType(cache, type as AuthEntryType).set(entryId, { bbId: m.id, data });

      if (type === AUTH_USER) {
        const email = (data.email as string | undefined)?.trim().toLowerCase();
        if (email) {
          cache.usersByEmail.set(email, entryId);
        }
      }
    } catch { /* skip malformed entries */ }
  }

  cache.loaded = true;
  authCache = cache;
  return cache;
}

async function upsertAuthEntry(
  type: AuthEntryType,
  id: string,
  data: Record<string, unknown>,
): Promise<Record<string, unknown>> {
  const cache = await getAuthCache();
  const bb = getClient();
  const aid = await getAuthAssistantId();
  const targetMap = getMapForType(cache, type);
  const existing = targetMap.get(id);

  if (existing) {
    await bb.deleteMemory(aid, existing.bbId);
  }

  const merged = existing ? { ...existing.data, ...data } : data;
  merged._id = id;

  const result = await bb.addMemory(aid, JSON.stringify(merged), {
    type,
    entryId: id,
    updatedAt: new Date().toISOString(),
  });

  const bbId = (result.memory_id ?? result.id ?? '') as string;
  targetMap.set(id, { bbId, data: merged });

  if (type === AUTH_USER) {
    const email = (merged.email as string | undefined)?.trim().toLowerCase();
    if (email) {
      cache.usersByEmail.set(email, id);
    }
  }

  return merged;
}

async function deleteAuthEntry(type: AuthEntryType, id: string): Promise<boolean> {
  const cache = await getAuthCache();
  const bb = getClient();
  const aid = await getAuthAssistantId();
  const targetMap = getMapForType(cache, type);

  const entry = targetMap.get(id);
  if (!entry) {
    return false;
  }

  await bb.deleteMemory(aid, entry.bbId);
  targetMap.delete(id);

  if (type === AUTH_USER) {
    const email = (entry.data.email as string | undefined)?.trim().toLowerCase();
    if (email) {
      cache.usersByEmail.delete(email);
    }
  }

  return true;
}

function invalidateAuthCache(): void {
  authCache = null;
  logger.info('[AuthStore] Cache invalidated — will reload from Backboard on next access');
}

export {
  AUTH_USER,
  AUTH_TOKEN,
  AUTH_SESSION,
  getAuthCache,
  upsertAuthEntry,
  deleteAuthEntry,
  getAuthAssistantId,
  invalidateAuthCache,
};

export type { AuthCache, CachedEntry, AuthEntryType };
