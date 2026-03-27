import { spawn } from 'node:child_process';

export function commandName(binary) {
  return process.platform === 'win32' ? `${binary}.cmd` : binary;
}

export function spawnService(command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: process.platform !== 'win32',
  });

  let output = '';
  child.stdout.on('data', (chunk) => {
    output += chunk.toString();
  });
  child.stderr.on('data', (chunk) => {
    output += chunk.toString();
  });
  child.__output = () => output;
  return child;
}

export async function waitForUrl(url, child, timeoutMs = 30000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (child?.exitCode !== null) {
      throw new Error(`Service exited early while waiting for ${url}\n${child.__output?.() ?? ''}`);
    }

    try {
      const response = await fetch(url);
      if (response.ok) {
        return;
      }
    } catch {
      // keep polling
    }

    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(`Timed out waiting for ${url}\n${child?.__output?.() ?? ''}`);
}

export async function ensureService({ name, url, command, args, cwd }) {
  try {
    const response = await fetch(url);
    if (response.ok) {
      return { name, url, reused: true, child: null };
    }
  } catch {
    // start below
  }

  const child = spawnService(command, args, cwd);
  await waitForUrl(url, child);
  return { name, url, reused: false, child };
}

export function stopService(child) {
  if (!child) {
    return;
  }
  if (process.platform === 'win32') {
    child.kill('SIGTERM');
    return;
  }
  process.kill(-child.pid, 'SIGTERM');
}
