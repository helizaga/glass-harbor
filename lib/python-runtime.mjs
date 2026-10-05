import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { spawn } from 'node:child_process';

import { repoRoot } from './song-contract.mjs';

export function resolvePythonExecutable() {
  const explicit = (process.env.GLASS_HARBOR_PYTHON ?? '').trim();
  if (explicit) {
    return explicit;
  }

  const localVenv = process.platform === 'win32'
    ? join(repoRoot, '.glass-harbor-venv', 'Scripts', 'python.exe')
    : join(repoRoot, '.glass-harbor-venv', 'bin', 'python');
  if (existsSync(localVenv)) {
    return localVenv;
  }

  return process.platform === 'win32' ? 'python' : 'python3';
}

export function runPythonJson(scriptPath, payload, { env = {}, cwd = repoRoot } = {}) {
  const python = resolvePythonExecutable();
  return new Promise((resolve, reject) => {
    const child = spawn(python, [scriptPath], {
      cwd,
      env: {
        ...process.env,
        ...env,
      },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });

    // A failed spawn can emit both 'error' and 'exit'; settle only once.
    let settled = false;
    child.on('error', (error) => {
      settled = true;
      reject(error);
    });
    child.on('exit', (code) => {
      if (settled) {
        return;
      }
      settled = true;
      if (code !== 0) {
        reject(new Error(stderr.trim() || `Python helper exited with code ${code}`));
        return;
      }

      try {
        resolve(JSON.parse(stdout));
      } catch (error) {
        reject(new Error(`Failed to parse Python helper output: ${error.message}\n${stdout}`));
      }
    });

    child.stdin.end(`${JSON.stringify(payload)}\n`);
  });
}
