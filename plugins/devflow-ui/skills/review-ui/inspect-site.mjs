#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const usage = 'usage: node inspect-site.mjs [path-or-url-or-file ...] [--config FILE] [--base URL] [--widths 375,1440] [--out DIR] [--allow rule,rule] [--app] [--json]';

const args = process.argv.slice(2);
if (args.includes('-h') || args.includes('--help')) { console.log(usage); process.exit(0); }
const take = (name) => { const i = args.indexOf('--' + name); if (i === -1) return undefined; const v = args[i + 1]; args.splice(i, 2); return v; };

const configPath = resolve(take('config') ?? '.claude/ui-review.json');
let config = {};
if (existsSync(configPath)) {
  try { config = JSON.parse(readFileSync(configPath, 'utf8')); }
  catch (e) { console.error(`Cannot parse ${configPath}: ${e.message}`); process.exit(2); }
}

const base = (take('base') ?? config.base ?? 'http://localhost:3000').replace(/\/$/, '');
const widths = take('widths') ?? (config.widths ?? [375, 1440]).join(',');
const outRoot = resolve(take('out') ?? config.out ?? join(tmpdir(), 'review-ui', basename(resolve('.'))));
const allowed = config.allow ?? {};
const allow = [...new Set([...(Array.isArray(allowed) ? allowed : Object.keys(allowed)), ...(take('allow') ?? '').split(',').filter(Boolean)])];
const json = args.includes('--json');
const app = args.includes('--app');
const targets = args.filter((a) => !a.startsWith('--'));
if (!targets.length) targets.push(...(config.paths ?? ['/']));

const isUrl = (t) => /^https?:\/\//.test(t);
const isFile = (t) => !t.startsWith('/') && !isUrl(t) && existsSync(t);
const resolveTarget = (t) => (isUrl(t) || isFile(t) ? t : base + (t.startsWith('/') ? t : '/' + t));

if (targets.some((t) => !isUrl(t) && !isFile(t))) {
  try {
    const r = await fetch(base + '/', { signal: AbortSignal.timeout(3000) });
    if (r.status >= 500) throw new Error('HTTP ' + r.status);
  } catch {
    console.error(`Cannot reach ${base}. Start the dev server first, or pass --base.`);
    process.exit(2);
  }
}

console.error(`config: ${existsSync(configPath) ? configPath : 'none'} · allow: ${allow.join(',') || 'none'} · out: ${outRoot}`);

let failed = false;
for (const t of targets) {
  const label = t.replace(/^https?:\/\/[^/]+/, '').replace(/^\/?\??/, '').replace(/[^a-z0-9]+/gi, '-').replace(/^-|-$/g, '') || 'root';
  const res = spawnSync(process.execPath, [
    join(here, 'vendor/taste-skill/scripts/inspect.mjs'), resolveTarget(t),
    '--out', join(outRoot, label), '--widths', widths,
    ...(allow.length ? ['--allow', allow.join(',')] : []), ...(json ? ['--json'] : []), ...(app ? ['--app'] : []),
  ], { stdio: 'inherit' });
  if (res.status !== 0) failed = true;
}
process.exit(failed ? 1 : 0);
