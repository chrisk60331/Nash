import { logger } from '@librechat/data-schemas';
import {
  upsertMessage,
  deleteMsg,
  getMsgFromCache,
  getMsgsByConvo,
  getUserCache,
  deleteMsgsByConvo,
} from './userStore';

export async function saveMessageBB(
  req: { user: { id: string }; body?: Record<string, unknown>; config?: Record<string, unknown> },
  params: Record<string, unknown>,
  metadata?: { context?: string },
): Promise<Record<string, unknown> | undefined> {
  if (!req?.user?.id) {
    throw new Error('User not authenticated');
  }

  const conversationId = params.conversationId as string;
  if (!conversationId) {
    logger.warn(`[saveMessageBB] Invalid conversation ID: ${conversationId}`);
    logger.info(`---saveMessageBB context: ${metadata?.context}`);
    return;
  }

  try {
    const messageId = (params.newMessageId ?? params.messageId) as string;
    const update: Record<string, unknown> = {
      ...params,
      user: req.user.id,
      messageId,
    };

    update.expiredAt = null;

    if (update.tokenCount != null && isNaN(update.tokenCount as number)) {
      logger.warn(`Resetting invalid tokenCount for message ${messageId}: ${update.tokenCount}`);
      update.tokenCount = 0;
    }

    return await upsertMessage(req.user.id, messageId, update);
  } catch (err) {
    logger.error('[saveMessageBB] Error saving message:', err);
    logger.info(`---saveMessageBB context: ${metadata?.context}`);

    return {
      ...params,
      messageId: params.messageId,
      user: req.user.id,
    };
  }
}

export async function bulkSaveMessagesBB(
  messages: Array<Record<string, unknown>>,
): Promise<{ modifiedCount: number; upsertedCount: number }> {
  let upsertedCount = 0;
  for (const msg of messages) {
    const userId = msg.user as string;
    const messageId = msg.messageId as string;
    if (userId && messageId) {
      await upsertMessage(userId, messageId, msg);
      upsertedCount++;
    }
  }
  return { modifiedCount: 0, upsertedCount };
}

export async function recordMessageBB(params: Record<string, unknown>): Promise<Record<string, unknown>> {
  const userId = params.user as string;
  const messageId = params.messageId as string;
  return upsertMessage(userId, messageId, params);
}

export async function updateMessageTextBB(
  req: { user: { id: string } },
  { messageId, text }: { messageId: string; text: string },
): Promise<void> {
  const existing = await getMsgFromCache(req.user.id, messageId);
  if (existing) {
    await upsertMessage(req.user.id, messageId, { ...existing, text });
  }
}

export async function updateMessageBB(
  req: { user: { id: string } },
  message: Record<string, unknown>,
  metadata?: { context?: string },
): Promise<Record<string, unknown>> {
  const { messageId, ...update } = message;
  const mid = messageId as string;
  const existing = await getMsgFromCache(req.user.id, mid);

  if (!existing) {
    throw new Error('Message not found or user not authorized.');
  }

  const merged = { ...existing, ...update };
  await upsertMessage(req.user.id, mid, merged);

  return {
    messageId: mid,
    conversationId: merged.conversationId,
    parentMessageId: merged.parentMessageId,
    sender: merged.sender,
    text: merged.text,
    isCreatedByUser: merged.isCreatedByUser,
    tokenCount: merged.tokenCount,
    feedback: merged.feedback,
  };
}

export async function deleteMessagesSinceBB(
  req: { user: { id: string } },
  { messageId, conversationId }: { messageId: string; conversationId: string },
): Promise<{ deletedCount: number } | undefined> {
  const msg = await getMsgFromCache(req.user.id, messageId);
  if (!msg) {
    return undefined;
  }

  const msgTime = new Date(msg.createdAt as string).getTime();
  const cache = await getUserCache(req.user.id);
  const toDelete: string[] = [];

  for (const [mid, entry] of cache.msgs.entries()) {
    if (entry.data.conversationId !== conversationId) {
      continue;
    }
    if (entry.data.user !== req.user.id) {
      continue;
    }
    const t = new Date(entry.data.createdAt as string).getTime();
    if (t > msgTime) {
      toDelete.push(mid);
    }
  }

  for (const mid of toDelete) {
    await deleteMsg(req.user.id, mid);
  }

  return { deletedCount: toDelete.length };
}

export async function getMessagesBB(
  filter: Record<string, unknown>,
  select?: string,
): Promise<Record<string, unknown>[]> {
  const conversationId = filter.conversationId as string | undefined;
  let user = filter.user as string | undefined;

  if (!conversationId) {
    return [];
  }

  if (!user) {
    const { findUserForConvo } = await import('./userStore');
    user = await findUserForConvo(conversationId);
    if (!user) {
      return [];
    }
  }

  let results = await getMsgsByConvo(user, conversationId);

  const messageId = filter.messageId as string | undefined;
  if (messageId) {
    results = results.filter((m) => m.messageId === messageId);
  }

  if (select === '_id') {
    return results.map((m) => ({ _id: m.messageId ?? m._id }));
  }

  return results;
}

export async function getMessageBB(filter: {
  user: string;
  messageId: string;
}): Promise<Record<string, unknown> | null> {
  return getMsgFromCache(filter.user, filter.messageId);
}

export async function deleteMessagesBB(
  filter: Record<string, unknown>,
): Promise<{ deletedCount: number }> {
  let conversationId = filter.conversationId as string | Record<string, string[]> | undefined;
  const messageId = filter.messageId as string | undefined;
  const user = filter.user as string | undefined;

  if (messageId && user) {
    const deleted = await deleteMsg(user, messageId);
    return { deletedCount: deleted ? 1 : 0 };
  }

  if (typeof conversationId === 'object' && conversationId !== null) {
    const inList = (conversationId as Record<string, string[]>).$in;
    if (Array.isArray(inList)) {
      let total = 0;
      for (const cid of inList) {
        if (user) {
          total += await deleteMsgsByConvo(user, cid);
        }
      }
      return { deletedCount: total };
    }
  }

  if (typeof conversationId === 'string' && user) {
    const count = await deleteMsgsByConvo(user, conversationId);
    return { deletedCount: count };
  }

  return { deletedCount: 0 };
}
