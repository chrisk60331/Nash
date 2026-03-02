import { backboardStorage } from './storage';

const MEMORY_TYPE = 'librechat_memory';

interface UserMemory {
  key: string;
  value: string;
  tokenCount: number;
  updated_at: Date;
}

interface MemoriesResponse {
  memories: UserMemory[];
  totalTokens: number;
  tokenLimit: number | null;
  charLimit: number;
  usagePercentage: number | null;
}

export async function getAllUserMemoriesBB(userId: string): Promise<UserMemory[]> {
  const items = await backboardStorage.listByType(MEMORY_TYPE, userId);
  return items.map((item) => ({
    key: (item.metadata.key as string) ?? '',
    value: item.content,
    tokenCount: (item.metadata.tokenCount as number) ?? 0,
    updated_at: new Date(item.updated_at ?? item.created_at ?? Date.now()),
  }));
}

export async function createMemoryBB(params: {
  userId: string;
  key: string;
  value: string;
  tokenCount: number;
}): Promise<{ ok: boolean }> {
  const existing = await backboardStorage.findByMetadata(
    MEMORY_TYPE,
    'key',
    params.key,
    params.userId,
  );

  if (existing) {
    throw new Error(`Memory with key "${params.key}" already exists`);
  }

  await backboardStorage.createItem(params.value, {
    type: MEMORY_TYPE,
    userId: params.userId,
    key: params.key,
    tokenCount: params.tokenCount,
  });

  return { ok: true };
}

export async function setMemoryBB(params: {
  userId: string;
  key: string;
  value: string;
  tokenCount: number;
}): Promise<{ ok: boolean }> {
  const existing = await backboardStorage.findByMetadata(
    MEMORY_TYPE,
    'key',
    params.key,
    params.userId,
  );

  if (existing) {
    await backboardStorage.deleteItem(existing.id);
  }

  await backboardStorage.createItem(params.value, {
    type: MEMORY_TYPE,
    userId: params.userId,
    key: params.key,
    tokenCount: params.tokenCount,
  });

  return { ok: true };
}

export async function deleteMemoryBB(params: {
  userId: string;
  key: string;
}): Promise<{ ok: boolean }> {
  const existing = await backboardStorage.findByMetadata(
    MEMORY_TYPE,
    'key',
    params.key,
    params.userId,
  );

  if (!existing) {
    return { ok: false };
  }

  const deleted = await backboardStorage.deleteItem(existing.id);
  return { ok: deleted };
}
