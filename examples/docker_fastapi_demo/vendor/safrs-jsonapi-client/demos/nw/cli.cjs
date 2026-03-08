#!/usr/bin/env node
const path = require('node:path');

let client;
try {
  client = require('../../dist/index.js');
} catch (error) {
  const message = error instanceof Error ? error.message : String(error);
  console.error('Failed to load ../../dist/index.js:', message);
  console.error('Run `npm run build` first, then retry.');
  process.exit(1);
}

const {
  createDataProviderSync,
  loadAdminYamlFromFile,
  normalizeAdminYaml
} = client;

function printUsage() {
  console.log(
    'Usage: node demos/nw/cli.cjs [--admin-yaml <path>] [--api-url <url>] [--resource <name>] [--page <n>] [--limit <n>]'
  );
  console.log('');
  console.log('Defaults:');
  console.log('  --admin-yaml demos/nw/admin.yaml');
  console.log('  --resource Customer');
  console.log('  --page 1');
  console.log('  --limit 10');
}

function parsePositiveInt(value, fallback) {
  const parsed = Number.parseInt(value, 10);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return fallback;
  }
  return parsed;
}

function resolvePath(inputPath) {
  if (path.isAbsolute(inputPath)) {
    return inputPath;
  }
  return path.resolve(process.cwd(), inputPath);
}

function parseArgs(argv) {
  const args = {
    adminYaml: path.resolve(__dirname, 'admin.yaml'),
    apiUrl: undefined,
    resource: 'Customer',
    page: 1,
    limit: 10,
    help: false
  };

  for (let i = 0; i < argv.length; i += 1) {
    const token = argv[i];
    const next = argv[i + 1];

    if (token === '--help' || token === '-h') {
      args.help = true;
      continue;
    }

    if ((token === '--admin-yaml' || token === '--admin-yaml-file') && next) {
      args.adminYaml = resolvePath(next);
      i += 1;
      continue;
    }

    if ((token === '--api-url' || token === '--api-root') && next) {
      args.apiUrl = next;
      i += 1;
      continue;
    }

    if (token === '--resource' && next) {
      args.resource = next;
      i += 1;
      continue;
    }

    if (token === '--page' && next) {
      args.page = parsePositiveInt(next, args.page);
      i += 1;
      continue;
    }

    if (token === '--limit' && next) {
      args.limit = parsePositiveInt(next, args.limit);
      i += 1;
      continue;
    }
  }

  return args;
}

function ensureTrailingSlash(value) {
  return value.endsWith('/') ? value : `${value}/`;
}

function normalizeApiUrl(value) {
  const trimmed = String(value).trim();
  const withProtocol = trimmed.startsWith('//') ? `http:${trimmed}` : trimmed;
  const parsed = new URL(withProtocol);
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new Error(`Unsupported protocol in API URL: ${parsed.protocol}`);
  }
  return ensureTrailingSlash(parsed.toString());
}

function resolveApiUrl(args, schema) {
  if (args.apiUrl) {
    return normalizeApiUrl(args.apiUrl);
  }

  if (typeof schema.apiRoot === 'string' && schema.apiRoot.trim()) {
    return normalizeApiUrl(schema.apiRoot);
  }

  throw new Error('Unable to resolve API URL. Pass --api-url explicitly.');
}

function ensureResourceExists(schema, resource) {
  if (!schema.resources[resource]) {
    const known = Object.keys(schema.resources).slice(0, 10).join(', ');
    throw new Error(
      `Resource '${resource}' not found in schema. Known resources include: ${known}`
    );
  }
}

async function runListRequest(provider, args) {
  const result = await provider.getList(args.resource, {
    pagination: {
      page: args.page,
      perPage: args.limit
    }
  });

  console.log(
    `PASS getList resource=${args.resource} page=${args.page} limit=${args.limit} items=${result.data.length} total=${result.total}`
  );

  for (const [index, row] of result.data.entries()) {
    const id = row.id === undefined ? '(no id)' : String(row.id);
    console.log(`item[${index}] id=${id}`);
  }
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) {
    printUsage();
    return;
  }

  const rawYaml = await loadAdminYamlFromFile(args.adminYaml);
  const schema = normalizeAdminYaml(rawYaml);
  ensureResourceExists(schema, args.resource);

  const apiUrl = resolveApiUrl(args, schema);

  const provider = createDataProviderSync({
    schema,
    apiRoot: apiUrl,
    logger: console
  });

  await runListRequest(provider, args);
}

main().catch((error) => {
  const message = error instanceof Error ? error.message : String(error);
  console.error('NW demo failed:', message);
  process.exitCode = 1;
});
