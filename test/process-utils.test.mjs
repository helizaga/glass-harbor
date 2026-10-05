import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { once } from 'node:events';
import { test } from 'node:test';
import { ensureService, spawnService, stopService, waitForUrl } from '../lib/process-utils.mjs';

async function unusedPort() {
  const server = createServer();
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const port = server.address().port;
  await new Promise((resolve) => server.close(resolve));
  return port;
}

test('reuses an existing service without taking ownership or stopping it', async () => {
  const server = createServer((request, response) => response.end('ready'));
  server.listen(0, '127.0.0.1');
  await once(server, 'listening');
  const url = `http://127.0.0.1:${server.address().port}`;
  try {
    const service = await ensureService({ name: 'external', url, command: 'unused', args: [], cwd: process.cwd() });
    assert.equal(service.reused, true);
    assert.equal(service.child, null);
    stopService(service.child);
    assert.equal(await (await fetch(url)).text(), 'ready');
  } finally {
    await new Promise((resolve) => server.close(resolve));
  }
});

test('stops an owned service and its nested server process', { timeout: 10000 }, async () => {
  const port = await unusedPort();
  const serverCode = `require('node:http').createServer((q,r)=>r.end('ready')).listen(${port},'127.0.0.1')`;
  const wrapperCode = `require('node:child_process').spawn(process.execPath,['-e',${JSON.stringify(serverCode)}],{stdio:'inherit'}); setInterval(()=>{},1000)`;
  const child = spawnService(process.execPath, ['-e', wrapperCode], process.cwd());
  const url = `http://127.0.0.1:${port}`;
  try {
    await waitForUrl(url, child, 5000);
    stopService(child);
    let closed = false;
    for (let attempt = 0; attempt < 30; attempt += 1) {
      try { await fetch(url); } catch { closed = true; break; }
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    assert.equal(closed, true, 'nested server must not survive service cleanup');
  } finally {
    stopService(child);
  }
});

test('reports a failed startup with its diagnostic output', { timeout: 5000 }, async () => {
  const port = await unusedPort();
  await assert.rejects(
    ensureService({ name: 'broken', url: `http://127.0.0.1:${port}`, command: process.execPath,
      args: ['-e', "console.error('startup failed'); process.exit(1)"], cwd: process.cwd() }),
    /Service exited early[\s\S]*startup failed/,
  );
});
