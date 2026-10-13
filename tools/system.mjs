import { spawn } from 'node:child_process';
import { existsSync, mkdirSync } from 'node:fs';
import { setTimeout as delay } from 'node:timers/promises';
import net from 'node:net';
mkdirSync('.local', { recursive: true, mode: 0o700 });
const args = [
  'emulators:start',
  '--project',
  'demo-smartdb',
  '--export-on-exit',
  '.local/firebase',
];
if (existsSync('.local/firebase/firebase-export-metadata.json'))
  args.push('--import', '.local/firebase');
const child = spawn('node_modules/.bin/firebase', args, { stdio: 'inherit' });
let finished = false;
child.on('exit', (code) => {
  finished = true;
  process.exitCode = code || 0;
});
for (const signal of ['SIGINT', 'SIGTERM']) process.on(signal, () => child.kill(signal));
const ready = (port) =>
  new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port });
    socket.once('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.once('error', () => resolve(false));
    socket.setTimeout(500, () => {
      socket.destroy();
      resolve(false);
    });
  });
let started = false;
for (let i = 0; i < 120 && !finished; i++) {
  if ((await Promise.all([9099, 8080, 5000].map(ready))).every(Boolean)) {
    started = true;
    break;
  }
  await delay(1000);
}
if (started) {
  const bootstrap = spawn(process.execPath, ['cloud/scripts/bootstrap.mjs'], {
    stdio: 'inherit',
    env: {
      ...process.env,
      GCLOUD_PROJECT: 'demo-smartdb',
      FIREBASE_AUTH_EMULATOR_HOST: '127.0.0.1:9099',
      FIRESTORE_EMULATOR_HOST: '127.0.0.1:8080',
    },
  });
  bootstrap.on('exit', (code) => {
    if (code) console.error('Account setup failed; inspect the error above.');
  });
} else if (!finished) {
  console.error('Emulators did not become ready within two minutes.');
  child.kill('SIGINT');
}
