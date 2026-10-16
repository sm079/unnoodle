// pnpm serve: runs the whole app on this machine, with a production build of the web app, for using it from a phone
// (through Tailscale; see the README). In order: Postgres (with docker compose, if nothing answers yet), the
// migrations, the renderer (the dev one, when UNNOODLE_DEV_RENDERER_MAIN says where it is), the API and the worker, then
// next build and next start. Each line of output starts with the name of the process it came from, and Ctrl+C stops
// all of them.
//
// Settings come from the environment or the repo-root .env (see .env.example).

import { spawn, spawnSync } from 'node:child_process';
import { once } from 'node:events';
import { createRequire } from 'node:module';
import { createConnection, createServer } from 'node:net';
import path from 'node:path';
import { createInterface } from 'node:readline';
import { setTimeout as sleep } from 'node:timers/promises';
import { fileURLToPath } from 'node:url';
import { styleText } from 'node:util';

const root = fileURLToPath(new URL('..', import.meta.url));
const apiDir = path.join(root, 'apps', 'api');
const webDir = path.join(root, 'apps', 'web');
const isWindows = process.platform === 'win32';

try {
  // Values already in the environment win
  process.loadEnvFile(path.join(root, '.env'));
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
}

// The same defaults as next.config.ts and the API's settings
const apiUrl = new URL(process.env.API_URL ?? 'http://127.0.0.1:8000');
const databaseUrl = new URL(process.env.UNNOODLE_DATABASE_URL ?? 'postgresql+psycopg://unnoodle:unnoodle@127.0.0.1:5432/unnoodle');
const rendererUrl = new URL(process.env.UNNOODLE_RENDERER_URL ?? 'http://127.0.0.1:8189');
const rendererMain = process.env.UNNOODLE_DEV_RENDERER_MAIN;
const rendererPython = process.env.UNNOODLE_DEV_RENDERER_PYTHON ?? 'python';
// A high port, clear of the blocks Hyper-V and WSL reserve on Windows (netsh interface ipv4 show excludedportrange
// protocol=tcp), so the port tailscale serve forwards to is still free after a reboot
const webPort = Number(process.env.UNNOODLE_WEB_PORT ?? 18300);
const webUrl = `http://127.0.0.1:${webPort}`;

const nextBin = createRequire(path.join(webDir, 'package.json')).resolve('next/dist/bin/next');

/** A reason to stop that needs no stack trace */
class Problem extends Error {}

const colors = {
  serve: 'bold',
  postgres: 'blue',
  migrate: 'blue',
  renderer: 'magenta',
  api: 'cyan',
  worker: 'yellow',
  build: 'green',
  web: 'green'
};
const labelWidth = Math.max(...Object.keys(colors).map(name => name.length));

function print(name, text) {
  const label = styleText(colors[name], `${name.padEnd(labelWidth)} |`);
  for (const line of text.split('\n')) process.stdout.write(`${label} ${line}\n`);
}

function say(text) {
  print('serve', text);
}

/** Processes started here that haven't exited */
const running = new Set();
let stopping = false;

/** Starts a command with its output prefixed by `name`. Resolves with its exit code; rejects if it can't start. */
function start(name, command, args, cwd = root) {
  const child = spawn(command, args, {
    cwd,
    // Python holds its output back when it isn't writing to a terminal
    env: { ...process.env, PYTHONUNBUFFERED: '1' },
    stdio: ['ignore', 'pipe', 'pipe'],
    // In its own process group, so that it and whatever it starts can be signalled together. Not on Windows, where
    // that means a console window of its own, and where Ctrl+C reaches every process on this console anyway.
    detached: !isWindows
  });
  running.add(child);
  for (const stream of [child.stdout, child.stderr]) {
    createInterface({ input: stream, crlfDelay: Infinity }).on('line', line => print(name, line));
  }
  return new Promise((resolve, reject) => {
    child.once('error', error => {
      running.delete(child);
      reject(error.code === 'ENOENT' ? new Problem(`Can't start ${name}: ${command} isn't installed, or isn't on PATH.`) : error);
    });
    child.once('exit', (code, signal) => {
      running.delete(child);
      resolve(code ?? signal);
    });
  });
}

/** Runs a step to the end. */
async function run(name, command, args, cwd) {
  const code = await start(name, command, args, cwd);
  if (code !== 0) throw new Problem(`${name} failed (exit code ${code}).`);
}

/** Starts something that should keep running, and stops everything if it doesn't. */
function keepRunning(name, command, args, cwd) {
  start(name, command, args, cwd).then(
    async code => {
      // On Windows a Ctrl+C reaches the children too, and one of them can exit before this process hears of it
      await sleep(250);
      if (!stopping) stop(`${name} exited (exit code ${code}).`);
    },
    error => stop(error.message)
  );
}

/**
 * Stops whatever is still running, politely first: the worker puts the job it's on back in the queue when it's
 * interrupted. Windows can't interrupt one console process from another, but its Ctrl+C reaches all of them anyway.
 * A process killed outright leaves its job to be taken again once the lease runs out.
 */
async function stop(reason, interrupted = false) {
  if (stopping) return;
  stopping = true;
  if (reason) say(reason);
  if (running.size > 0) say('Stopping everything…');
  for (const child of running) {
    if (!isWindows) signal(child, 'SIGINT');
    else if (!interrupted) kill(child);
  }
  await Promise.race([Promise.all([...running].map(child => once(child, 'exit'))), sleep(10_000)]);
  for (const child of running) kill(child);
  process.exit(reason ? 1 : 0);
}

/** Ends a process and everything it started, at once */
function kill(child) {
  if (child.pid === undefined) return;
  if (isWindows) spawnSync('taskkill', ['/pid', String(child.pid), '/t', '/f'], { stdio: 'ignore' });
  else signal(child, 'SIGKILL');
}

function signal(child, name) {
  try {
    process.kill(-child.pid, name);
  } catch {
    // Already gone
  }
}

for (const name of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
  process.on(name, () => {
    if (!stopping) return stop(undefined, true);
    // A second Ctrl+C doesn't wait
    for (const child of running) kill(child);
    process.exit(130);
  });
}

function portOf(url) {
  return Number(url.port || (url.protocol === 'https:' ? 443 : 80));
}

/** Why nothing can listen on host:port right now (an error code), or null if something could */
function portProblem(host, port) {
  return new Promise(resolve => {
    const server = createServer();
    server.once('error', error => resolve(error.code));
    server.listen(port, host, () => server.close(() => resolve(null)));
  });
}

async function checkPorts(ports) {
  const problems = [];
  for (const { what, host, port, setting } of ports) {
    const code = await portProblem(host, port);
    if (code === 'EADDRINUSE') {
      problems.push(`Port ${port} is in use, so ${what} can't listen on it. Stop what's using it, or set ${setting} to use another.`);
    } else if (code === 'EACCES') {
      problems.push(`Port ${port} is reserved by the system, so ${what} can't listen on it. Set ${setting} to use another.`);
    } else if (code) problems.push(`${what} can't listen on ${host}:${port} (${code}).`);
  }
  if (problems.length > 0) throw new Problem(problems.join('\n'));
}

function accepts(host, port) {
  const socket = createConnection({ host, port, timeout: 1_000 });
  return new Promise(resolve => {
    socket.once('connect', () => resolve(true));
    socket.once('timeout', () => resolve(false));
    socket.once('error', () => resolve(false));
  }).finally(() => socket.destroy());
}

async function answers(url) {
  try {
    return (await fetch(url, { signal: AbortSignal.timeout(2_000) })).ok;
  } catch {
    return false;
  }
}

async function waitFor(url, seconds) {
  const deadline = Date.now() + seconds * 1_000;
  while (!stopping && Date.now() < deadline) {
    if (await answers(url)) return true;
    await sleep(500);
  }
  return false;
}

/** Says when a service starts answering, or that it hasn't after a while. */
async function report(what, url, seconds) {
  if (await waitFor(url, seconds)) say(`${what} is up`);
  else if (!stopping) say(`${what} hasn't answered at ${url} after ${seconds}s.`);
}

async function postgres() {
  const host = databaseUrl.hostname;
  const port = Number(databaseUrl.port || 5432);
  if (await accepts(host, port)) return;
  if (!['127.0.0.1', 'localhost'].includes(host)) throw new Problem(`Postgres isn't answering on ${host}:${port}.`);
  say(`Postgres isn't answering on ${host}:${port}; starting it with docker compose`);
  const code = await start('postgres', 'docker', ['compose', 'up', '--detach', '--wait']);
  if (code !== 0) throw new Problem(`docker compose couldn't start Postgres (exit code ${code}). Is Docker running?`);
}

/** How a phone on the tailnet reaches the web app, or what's missing (see the README) */
function phoneAccess() {
  const status = tailscale('status');
  if (status === undefined) return 'To use it from your phone, set up Tailscale (see the README).';
  if (status?.BackendState !== 'Running') return "Tailscale isn't connected, so your phone can't reach this yet.";
  const serve = tailscale('serve', 'status') ?? {};
  const here = [`http://127.0.0.1:${webPort}`, `http://localhost:${webPort}`];
  for (const [address, site] of Object.entries(serve.Web ?? {})) {
    if (!Object.values(site.Handlers ?? {}).some(handler => here.includes(handler.Proxy?.replace(/\/$/, '')))) continue;
    const split = address.lastIndexOf(':');
    const host = address.slice(0, split);
    const port = address.slice(split + 1);
    const scheme = serve.TCP?.[port]?.HTTP ? 'http' : 'https';
    return `On your phone: ${scheme}://${host}${port === (scheme === 'https' ? '443' : '80') ? '' : `:${port}`}`;
  }
  return `To reach it from your phone, run this once: tailscale serve --bg ${webPort}`;
}

/** A tailscale command's JSON output: undefined when there's no tailscale CLI, null when the command fails */
function tailscale(...args) {
  const result = spawnSync('tailscale', [...args, '--json'], { encoding: 'utf8', timeout: 5_000 });
  if (result.error?.code === 'ENOENT') return undefined;
  try {
    return result.status === 0 ? JSON.parse(result.stdout) : null;
  } catch {
    return null;
  }
}

async function main() {
  // A renderer that already answers is used as it is: it takes a while to start, and it may be a real one
  const rendererStats = new URL('/system_stats', rendererUrl).href;
  const rendererRunning = await answers(rendererStats);
  const startRenderer = !rendererRunning && rendererMain !== undefined;

  // An API or web app that is already running may be older code, so they aren't reused
  await checkPorts([
    { what: 'the API', host: apiUrl.hostname, port: portOf(apiUrl), setting: 'API_URL' },
    { what: 'the web app', host: '127.0.0.1', port: webPort, setting: 'UNNOODLE_WEB_PORT' },
    ...(startRenderer
      ? [{ what: 'the renderer', host: rendererUrl.hostname, port: portOf(rendererUrl), setting: 'UNNOODLE_RENDERER_URL' }]
      : [])
  ]);
  await postgres();
  await run('migrate', 'uv', ['run', 'alembic', 'upgrade', 'head'], apiDir);

  if (rendererRunning) say(`Using the renderer already running at ${rendererUrl.origin}`);
  else if (startRenderer) {
    keepRunning('renderer', rendererPython, [
      '-s',
      rendererMain,
      '--base-directory',
      path.join(root, 'dev', 'renderer'),
      '--listen',
      rendererUrl.hostname,
      '--port',
      String(portOf(rendererUrl)),
      '--cpu',
      '--disable-auto-launch',
      // The dev pipelines need neither the paid API nodes nor the asset database
      '--disable-partner-nodes',
      '--disable-assets'
    ]);
    report('The renderer', rendererStats, 120);
  } else {
    say(
      `Nothing answers at ${rendererUrl.origin}, so generations wait in the queue until the renderer is up.\n` +
        'Set UNNOODLE_DEV_RENDERER_MAIN to start the dev one from here.'
    );
  }
  keepRunning('api', 'uv', ['run', 'uvicorn', 'app.main:app', '--host', apiUrl.hostname, '--port', String(portOf(apiUrl))], apiDir);
  keepRunning('worker', 'uv', ['run', 'python', '-m', 'app.worker'], apiDir);
  report('The API', new URL('/health', apiUrl).href, 60);

  await run('build', process.execPath, [nextBin, 'build'], webDir);
  keepRunning('web', process.execPath, [nextBin, 'start', '--hostname', '127.0.0.1', '--port', String(webPort)], webDir);
  if (await waitFor(webUrl, 60)) {
    say(styleText('bold', `unnoodle is up at ${webUrl}`));
    say(phoneAccess());
    say('Ctrl+C stops everything.');
  }
}

main().catch(error => {
  if (!stopping) stop(error instanceof Problem ? error.message : (error.stack ?? String(error)));
});
