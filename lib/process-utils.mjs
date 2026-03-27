import { spawn } from 'node:child_process';

export function commandName(binary) {
  return process.platform === 'win32' ? `${binary}.cmd` : binary;
}

export function spawnService(command, args, cwd) {
  const child = spawn(command, args, {
    cwd,
    // Keep stdin open so long-lived dev servers like Vite do not exit
    // immediately when they detect a closed parent input stream.
    stdio: ['pipe', 'pipe', 'pipe'],
    detached: process.platform !== 'win32',
  });

  let output = '';
  let spawnError = null;
  child.stdout.on('data', (chunk) => {
    output += chunk.toString();
  });
  child.stderr.on('data', (chunk) => {
    output += chunk.toString();
  });
  child.on('error', (error) => {
    spawnError = error;
    output += `${error.message}\n`;
  });
  child.__output = () => output;
  child.__spawnError = () => spawnError;
  return child;
}

export async function waitForUrl(url, child, timeoutMs = 30000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (child?.__spawnError?.()) {
      throw new Error(`Failed to start service while waiting for ${url}\n${child.__output?.() ?? ''}`);
    }
    if (child && child.exitCode !== null) {
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
  if (typeof child.pid !== 'number') {
    return;
  }
  if (process.platform === 'win32') {
    child.kill('SIGTERM');
    return;
  }
  process.kill(-child.pid, 'SIGTERM');
}
