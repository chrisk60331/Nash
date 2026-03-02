#!/usr/bin/env node

/**
 * Fetches all LLM models from Backboard API and regenerates librechat.yaml
 *
 * Usage:
 *   node scripts/refresh-models.js
 *   BACKBOARD_API_KEY=xxx node scripts/refresh-models.js
 */

const fs = require('fs');
const path = require('path');

const API_KEY = process.env.BACKBOARD_API_KEY;
const BASE_URL = process.env.BACKBOARD_BASE_URL || 'https://app.backboard.io/api';
const OUTPUT = path.resolve(__dirname, '..', 'librechat.yaml');

if (!API_KEY) {
  const envPath = path.resolve(__dirname, '..', '.env');
  if (fs.existsSync(envPath)) {
    const envContent = fs.readFileSync(envPath, 'utf8');
    const match = envContent.match(/^BACKBOARD_API_KEY=(.+)$/m);
    if (match) {
      process.env.BACKBOARD_API_KEY = match[1].trim();
    }
  }
}

const apiKey = process.env.BACKBOARD_API_KEY;
if (!apiKey) {
  console.error('BACKBOARD_API_KEY not found in env or .env file');
  process.exit(1);
}

const PROVIDER_LABELS = {
  'openai': 'OpenAI',
  'anthropic': 'Anthropic',
  'google': 'Google',
  'xai': 'xAI',
  'openrouter': 'OpenRouter',
  'cohere': 'Cohere',
  'cerebras': 'Cerebras',
  'aws-bedrock': 'AWS Bedrock',
  'featherless': 'Featherless',
};

async function fetchProviders() {
  const res = await fetch(`${BASE_URL}/models/providers`, {
    headers: { 'X-API-Key': apiKey },
  });
  const data = await res.json();
  return data.providers || [];
}

async function fetchModelsForProvider(provider) {
  const allModels = [];
  let page = 1;
  const perPage = 100;

  while (true) {
    const url = `${BASE_URL}/models?provider=${encodeURIComponent(provider)}&page=${page}&per_page=${perPage}`;
    const res = await fetch(url, { headers: { 'X-API-Key': apiKey } });
    const data = await res.json();
    const models = data.models || [];

    if (models.length === 0) {
      break;
    }

    allModels.push(...models);

    if (models.length < perPage || allModels.length >= (data.total || Infinity)) {
      break;
    }
    page++;
  }

  return allModels.filter((m) => m.model_type === 'llm');
}

function buildYaml(providerModels) {
  const lines = [
    'version: 1.3.4',
    'cache: true',
    '',
    'interface:',
    '  endpointsMenu: true',
    '  modelSelect: true',
    '  parameters: true',
    '  sidePanel: true',
    '  presets: true',
    '  bookmarks: true',
    '  agents:',
    '    use: true',
    '    create: true',
    '',
    'endpoints:',
    '  custom:',
  ];

  const sorted = Object.keys(providerModels).sort((a, b) => {
    const order = ['openai', 'anthropic', 'google', 'xai', 'openrouter', 'cohere', 'cerebras', 'aws-bedrock', 'featherless'];
    return order.indexOf(a) - order.indexOf(b);
  });

  for (const provider of sorted) {
    const models = providerModels[provider];
    if (models.length === 0) {
      continue;
    }

    const label = PROVIDER_LABELS[provider] || provider;
    const titleModel = pickTitleModel(provider, models);

    lines.push(`    - name: '${label}'`);
    lines.push("      apiKey: '${BACKBOARD_API_KEY}'");
    lines.push("      baseURL: 'http://localhost:3080/api/backboard/v1'");
    lines.push('      models:');
    lines.push('        default:');

    for (const m of models) {
      lines.push(`          - '${provider}/${m.name}'`);
    }

    lines.push('        fetch: false');
    lines.push('      titleConvo: true');
    lines.push(`      titleModel: '${provider}/${titleModel}'`);
    lines.push(`      modelDisplayLabel: '${label}'`);
  }

  return lines.join('\n') + '\n';
}

function pickTitleModel(provider, models) {
  const preferences = {
    'openai': ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini'],
    'anthropic': ['claude-sonnet-4-6', 'claude-sonnet-4-20250514', 'claude-3-haiku-20240307'],
    'google': ['gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash-001'],
    'xai': ['grok-3-mini', 'grok-3'],
    'openrouter': ['google/gemini-2.5-flash', 'openai/gpt-4o-mini'],
    'cohere': ['command-a-03-2025', 'command-r-08-2024'],
    'cerebras': ['meta-llama/llama-3.1-8b-instruct'],
    'aws-bedrock': ['anthropic.claude-3-5-sonnet-20241022-v2:0'],
    'featherless': [],
  };

  const prefs = preferences[provider] || [];
  for (const pref of prefs) {
    if (models.some((m) => m.name === pref)) {
      return pref;
    }
  }
  return models[0].name;
}

async function main() {
  console.log('Fetching providers from Backboard...');
  const providers = await fetchProviders();
  console.log(`Found ${providers.length} providers: ${providers.join(', ')}`);

  const providerModels = {};
  let totalModels = 0;

  for (const provider of providers) {
    process.stdout.write(`  Fetching ${provider}...`);
    const models = await fetchModelsForProvider(provider);
    providerModels[provider] = models;
    totalModels += models.length;
    console.log(` ${models.length} LLM models`);
  }

  console.log(`\nTotal: ${totalModels} LLM models across ${providers.length} providers`);

  const yaml = buildYaml(providerModels);
  fs.writeFileSync(OUTPUT, yaml, 'utf8');
  console.log(`\nWritten to ${OUTPUT}`);
  console.log('Restart the backend to pick up changes.');
}

main().catch((err) => {
  console.error('Error:', err.message);
  process.exit(1);
});
