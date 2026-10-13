import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { randomBytes } from 'node:crypto';

if (!process.env.FIREBASE_AUTH_EMULATOR_HOST || !process.env.FIRESTORE_EMULATOR_HOST) {
  throw new Error('Bootstrap is local-emulator only. Configure both emulator hosts.');
}
const { auth } = await import('../src/firebase.js');
const { createProfile } = await import('../src/security.js');
const file = resolve('.local/admin.json');
let account,
  recovered = false;
try {
  account = JSON.parse(await readFile(file, 'utf8'));
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
  recovered = true;
  account = { email: 'admin@smartdb.local', password: randomBytes(18).toString('base64url') };
}
let record;
try {
  record = await auth.getUserByEmail(account.email);
} catch (error) {
  if (error.code !== 'auth/user-not-found') throw error;
  record = await auth.createUser({ ...account, displayName: 'SmartDB administrator' });
}
// Local-only recovery when an emulator export survives but its password file does not.
if (recovered) await auth.updateUser(record.uid, { password: account.password });
await createProfile(record.uid, account.email, 'SmartDB administrator', 'admin');
await mkdir(resolve('.local'), { recursive: true, mode: 0o700 });
await writeFile(file, JSON.stringify(account, null, 2) + '\n', { mode: 0o600 });
console.log(
  `\nSmartDB developer console: http://127.0.0.1:5000\nEmail: ${account.email}\nPassword: ${account.password}\nCredentials saved in .local/admin.json (not committed).\n`,
);
