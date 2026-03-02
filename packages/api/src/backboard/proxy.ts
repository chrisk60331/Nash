import crypto from 'crypto';
import { v4 as uuidv4 } from 'uuid';
import { logger } from '@librechat/data-schemas';
import { BackboardClient } from './client';
import type { Request, Response } from 'express';
import type {
  OpenAIChatMessage,
  OpenAIChatCompletionRequest,
  OpenAIChatCompletionChunk,
  OpenAIChatCompletionResponse,
} from './types';

let cachedClient: BackboardClient | null = null;
let cachedAssistantId: string | null = null;

/** Maps a conversation fingerprint to a Backboard threadId for thread reuse */
const threadCache = new Map<string, string>();

function getClient(): BackboardClient {
  if (cachedClient) {
    return cachedClient;
  }

  const apiKey = process.env.BACKBOARD_API_KEY;
  if (!apiKey) {
    throw new Error('BACKBOARD_API_KEY environment variable is required');
  }

  const baseUrl = process.env.BACKBOARD_BASE_URL ?? 'https://app.backboard.io/api';
  cachedClient = new BackboardClient(apiKey, baseUrl);
  return cachedClient;
}

async function getOrCreateAssistant(client: BackboardClient): Promise<string> {
  if (cachedAssistantId) {
    return cachedAssistantId;
  }

  const envId = process.env.BACKBOARD_ASSISTANT_ID;
  if (envId) {
    cachedAssistantId = envId;
    logger.info(`[Backboard] Using assistant from env: ${envId}`);
    return envId;
  }

  const assistants = await client.listAssistants();
  const existing = assistants.find((a) => a.name === 'LibreChat');
  if (existing) {
    cachedAssistantId = existing.assistant_id;
    logger.info(`[Backboard] Using existing assistant: ${cachedAssistantId}`);
    return cachedAssistantId;
  }

  const created = await client.createAssistant(
    'LibreChat',
    'LibreChat conversational assistant powered by Backboard',
  );
  cachedAssistantId = created.assistant_id;
  logger.info(`[Backboard] Created assistant: ${cachedAssistantId}`);
  return cachedAssistantId;
}

/**
 * Builds a deterministic fingerprint from the conversation's first user message
 * and the user ID, used to map conversations to persistent Backboard threads.
 */
function conversationFingerprint(messages: OpenAIChatMessage[], userId?: string): string {
  const firstUserMsg = messages.find((m) => m.role === 'user');
  const seed = `${userId ?? 'anon'}::${firstUserMsg?.content ?? ''}`;
  return crypto.createHash('sha256').update(seed).digest('hex').slice(0, 24);
}

async function getOrCreateThread(
  client: BackboardClient,
  assistantId: string,
  messages: OpenAIChatMessage[],
  userId?: string,
): Promise<{ threadId: string; isExisting: boolean }> {
  const fp = conversationFingerprint(messages, userId);
  const cached = threadCache.get(fp);
  if (cached) {
    return { threadId: cached, isExisting: true };
  }

  const thread = await client.createThread(assistantId);
  threadCache.set(fp, thread.thread_id);
  return { threadId: thread.thread_id, isExisting: false };
}

function buildPromptFromMessages(messages: OpenAIChatMessage[]): string {
  if (messages.length === 0) {
    return '';
  }

  if (messages.length === 1) {
    return messages[0].content ?? '';
  }

  const systemMessages = messages.filter((m) => m.role === 'system');
  const conversationMessages = messages.filter((m) => m.role !== 'system');

  const parts: string[] = [];

  if (systemMessages.length > 0) {
    const systemContent = systemMessages
      .map((m) => m.content)
      .filter(Boolean)
      .join('\n');
    parts.push(`[System Instructions]\n${systemContent}`);
  }

  if (conversationMessages.length > 1) {
    const history = conversationMessages.slice(0, -1);
    const historyLines = history
      .map((m) => {
        const label = m.role === 'user' ? 'User' : 'Assistant';
        return `${label}: ${m.content ?? ''}`;
      })
      .join('\n');
    parts.push(`[Conversation History]\n${historyLines}`);
  }

  const lastMessage = conversationMessages[conversationMessages.length - 1];
  if (lastMessage) {
    parts.push(`[Current Message]\n${lastMessage.content ?? ''}`);
  }

  return parts.join('\n\n');
}

function extractLatestUserMessage(messages: OpenAIChatMessage[]): string {
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'user' && messages[i].content) {
      return messages[i].content as string;
    }
  }
  return buildPromptFromMessages(messages);
}

function parseModelSpec(model: string): { provider?: string; modelName: string } {
  if (model.includes('/')) {
    const [provider, ...rest] = model.split('/');
    return { provider, modelName: rest.join('/') };
  }
  return { modelName: model };
}

export async function handleChatCompletions(req: Request, res: Response): Promise<void> {
  try {
    const body = req.body as OpenAIChatCompletionRequest;
    const { messages, model, stream } = body;

    if (!messages || messages.length === 0) {
      res.status(400).json({ error: { message: 'messages array is required', type: 'invalid_request_error' } });
      return;
    }

    const client = getClient();
    const assistantId = await getOrCreateAssistant(client);
    const userId = body.user as string | undefined;
    const { threadId, isExisting } = await getOrCreateThread(client, assistantId, messages, userId);
    const { provider, modelName } = parseModelSpec(model ?? 'gpt-4o');

    const prompt = isExisting
      ? extractLatestUserMessage(messages)
      : buildPromptFromMessages(messages);

    if (stream) {
      await handleStreamingResponse(res, client, threadId, prompt, modelName, provider);
    } else {
      await handleNonStreamingResponse(res, client, threadId, prompt, model, modelName, provider);
    }
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Internal server error';
    logger.error(`[Backboard Proxy] Error: ${message}`);
    if (!res.headersSent) {
      res.status(500).json({ error: { message, type: 'server_error' } });
    }
  }
}

async function handleStreamingResponse(
  res: Response,
  client: BackboardClient,
  threadId: string,
  prompt: string,
  modelName: string,
  provider?: string,
): Promise<void> {
  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache, no-transform');
  res.setHeader('Connection', 'keep-alive');
  res.setHeader('X-Accel-Buffering', 'no');

  const completionId = `chatcmpl-bb-${uuidv4().slice(0, 12)}`;
  const created = Math.floor(Date.now() / 1000);

  const roleChunk: OpenAIChatCompletionChunk = {
    id: completionId,
    object: 'chat.completion.chunk',
    created,
    model: modelName,
    choices: [{ index: 0, delta: { role: 'assistant' }, finish_reason: null }],
  };
  res.write(`data: ${JSON.stringify(roleChunk)}\n\n`);

  let totalInputTokens = 0;
  let totalOutputTokens = 0;

  for await (const event of client.streamMessage(threadId, prompt, {
    llmProvider: provider,
    modelName,
    memory: 'Auto',
  })) {
    if (res.writableEnded) {
      break;
    }

    if (event.type === 'content_streaming' && event.content) {
      const chunk: OpenAIChatCompletionChunk = {
        id: completionId,
        object: 'chat.completion.chunk',
        created,
        model: modelName,
        choices: [{ index: 0, delta: { content: event.content }, finish_reason: null }],
      };
      res.write(`data: ${JSON.stringify(chunk)}\n\n`);
    }

    if (event.type === 'message_complete' || event.type === 'run_ended') {
      if (event.input_tokens) {
        totalInputTokens = event.input_tokens;
      }
      if (event.output_tokens) {
        totalOutputTokens = event.output_tokens;
      }
    }
  }

  const stopChunk: OpenAIChatCompletionChunk = {
    id: completionId,
    object: 'chat.completion.chunk',
    created,
    model: modelName,
    choices: [{ index: 0, delta: {}, finish_reason: 'stop' }],
    usage: {
      prompt_tokens: totalInputTokens,
      completion_tokens: totalOutputTokens,
      total_tokens: totalInputTokens + totalOutputTokens,
    },
  };
  res.write(`data: ${JSON.stringify(stopChunk)}\n\n`);
  res.write('data: [DONE]\n\n');
  res.end();
}

async function handleNonStreamingResponse(
  res: Response,
  client: BackboardClient,
  threadId: string,
  prompt: string,
  model: string,
  modelName: string,
  provider?: string,
): Promise<void> {
  const contentParts: string[] = [];
  let totalInputTokens = 0;
  let totalOutputTokens = 0;

  for await (const event of client.streamMessage(threadId, prompt, {
    llmProvider: provider,
    modelName,
    memory: 'Auto',
  })) {
    if (event.type === 'content_streaming' && event.content) {
      contentParts.push(event.content);
    }
    if (event.type === 'message_complete' || event.type === 'run_ended') {
      if (event.input_tokens) {
        totalInputTokens = event.input_tokens;
      }
      if (event.output_tokens) {
        totalOutputTokens = event.output_tokens;
      }
    }
  }

  const response: OpenAIChatCompletionResponse = {
    id: `chatcmpl-bb-${uuidv4().slice(0, 12)}`,
    object: 'chat.completion',
    created: Math.floor(Date.now() / 1000),
    model: model ?? modelName,
    choices: [
      {
        index: 0,
        message: { role: 'assistant', content: contentParts.join('') },
        finish_reason: 'stop',
      },
    ],
    usage: {
      prompt_tokens: totalInputTokens,
      completion_tokens: totalOutputTokens,
      total_tokens: totalInputTokens + totalOutputTokens,
    },
  };

  res.json(response);
}

let cachedModels: { id: string; object: string; created: number; owned_by: string }[] | null = null;
let modelsCacheExpiry = 0;

const MODELS_CACHE_TTL_MS = 3600_000;

async function fetchBackboardModels(): Promise<
  { id: string; object: string; created: number; owned_by: string }[]
> {
  const now = Date.now();
  if (cachedModels && now < modelsCacheExpiry) {
    return cachedModels;
  }

  const apiKey = process.env.BACKBOARD_API_KEY;
  const baseUrl = process.env.BACKBOARD_BASE_URL ?? 'https://app.backboard.io/api';

  if (!apiKey) {
    return [];
  }

  const providersRes = await fetch(`${baseUrl}/models/providers`, {
    headers: { 'X-API-Key': apiKey },
  });
  const { providers = [] } = (await providersRes.json()) as { providers: string[] };

  const allModels: { id: string; object: string; created: number; owned_by: string }[] = [];

  for (const provider of providers) {
    const modelsRes = await fetch(
      `${baseUrl}/models?provider=${encodeURIComponent(provider)}`,
      { headers: { 'X-API-Key': apiKey } },
    );
    const data = (await modelsRes.json()) as {
      models: { name: string; model_type: string; provider: string }[];
    };

    for (const m of data.models ?? []) {
      if (m.model_type !== 'llm') {
        continue;
      }
      allModels.push({
        id: `${m.provider}/${m.name}`,
        object: 'model',
        created: 1700000000,
        owned_by: m.provider,
      });
    }
  }

  cachedModels = allModels;
  modelsCacheExpiry = now + MODELS_CACHE_TTL_MS;
  logger.info(`[Backboard] Cached ${allModels.length} models from ${providers.length} providers`);
  return allModels;
}

export async function handleListModels(_req: Request, res: Response): Promise<void> {
  try {
    const models = await fetchBackboardModels();
    res.json({ object: 'list', data: models });
  } catch (err) {
    logger.error('[Backboard] Error fetching models:', err);
    res.json({ object: 'list', data: [] });
  }
}
