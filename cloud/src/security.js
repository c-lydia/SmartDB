import { createHash, randomBytes } from 'node:crypto';
import { db, auth, isEmulator } from './firebase.js';

export const hash = (value) => createHash('sha256').update(value).digest('hex');
export const secret = () => randomBytes(32).toString('hex');
export const now = () => new Date().toISOString();
export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.status = status;
    this.code = code;
  }
}
export const fail = (status, code, message) => {
  throw new ApiError(status, code, message);
};
export async function nextId(tx, name) {
  const ref = db.doc(`counters/${name}`),
    snap = await tx.get(ref);
  return { ref, value: (snap.data()?.value || 0) + 1 };
}
export async function createProfile(uid, email, name, role = 'viewer') {
  return db.runTransaction(async (tx) => {
    const ref = db.doc(`users/${uid}`),
      existing = await tx.get(ref);
    if (existing.exists) return existing.data();
    const id = await nextId(tx, 'users');
    const user = { id: id.value, email, name, role };
    tx.set(id.ref, { value: id.value });
    tx.create(ref, user);
    return user;
  });
}
async function identity(path, data, refresh = false) {
  const emulator = process.env.FIREBASE_AUTH_EMULATOR_HOST;
  const base = emulator
    ? `http://${emulator}/${refresh ? 'securetoken.googleapis.com' : 'identitytoolkit.googleapis.com'}`
    : `https://${refresh ? 'securetoken.googleapis.com' : 'identitytoolkit.googleapis.com'}`;
  const key = process.env.FIREBASE_WEB_API_KEY || (isEmulator ? 'demo-key' : '');
  if (!key) fail(503, 'AUTH_NOT_CONFIGURED', 'Authentication is not configured.');
  const response = await fetch(`${base}/v1/${path}?key=${encodeURIComponent(key)}`, {
    method: 'POST',
    headers: { 'Content-Type': refresh ? 'application/x-www-form-urlencoded' : 'application/json' },
    body: refresh ? new URLSearchParams(data) : JSON.stringify(data),
    signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) fail(401, 'UNAUTHORIZED', 'Invalid or expired credentials.');
  return response.json();
}
async function pair(result, old = null) {
  const access = result.idToken || result.id_token,
    uid = result.localId || result.user_id;
  const refreshToken = 'sdb_refresh_' + secret();
  const session = {
    uid,
    firebase_refresh: result.refreshToken || result.refresh_token,
    access_hash: hash(access),
    expires_at: Date.now() + 30 * 86400000,
  };
  await db.runTransaction(async (tx) => {
    if (old) {
      const snap = await tx.get(old.ref);
      if (!snap.exists || snap.data().uid !== uid)
        fail(401, 'UNAUTHORIZED', 'Refresh token already used.');
      tx.delete(old.ref);
      tx.delete(db.doc(`access_sessions/${old.data.access_hash}`));
    }
    tx.create(db.doc(`sessions/${hash(refreshToken)}`), session);
    tx.set(db.doc(`access_sessions/${hash(access)}`), { uid, expires_at: Date.now() + 3600000 });
  });
  return {
    access_token: access,
    refresh_token: refreshToken,
    token_type: 'bearer',
    expires_in: 3600,
  };
}
export async function login(data) {
  const result = await identity('accounts:signInWithPassword', {
    ...data,
    returnSecureToken: true,
  });
  if (!(await db.doc(`users/${result.localId}`).get()).exists)
    fail(403, 'NOT_PROVISIONED', 'Account has not been provisioned.');
  return pair(result);
}
export async function refresh(token) {
  const ref = db.doc(`sessions/${hash(token)}`),
    snap = await ref.get();
  if (!snap.exists || snap.data().expires_at < Date.now())
    fail(401, 'UNAUTHORIZED', 'Invalid or expired credentials.');
  const result = await identity(
    'token',
    { grant_type: 'refresh_token', refresh_token: snap.data().firebase_refresh },
    true,
  );
  return pair(result, { ref, data: snap.data() });
}
export async function logout(uid, token) {
  await db.runTransaction(async (tx) => {
    const ref = db.doc(`sessions/${hash(token)}`),
      snap = await tx.get(ref);
    if (!snap.exists) return;
    if (snap.data().uid !== uid) fail(403, 'FORBIDDEN', 'Not permitted.');
    tx.delete(ref);
    tx.delete(db.doc(`access_sessions/${snap.data().access_hash}`));
  });
}
export async function authenticate(req, res, next) {
  const token = /^Bearer ([^\s]+)$/.exec(req.get('Authorization') || '')?.[1];
  if (!token) fail(401, 'UNAUTHORIZED', 'Authentication required.');
  if (token.startsWith('sdb_device_')) {
    const doc = await db.doc(`device_keys/${hash(token)}`).get();
    if (!doc.exists) fail(401, 'UNAUTHORIZED', 'Invalid device credential.');
    req.actor = { kind: 'device', device_id: doc.data().device_id };
  } else {
    let decoded;
    try {
      decoded = await auth.verifyIdToken(token, true);
    } catch {
      fail(401, 'UNAUTHORIZED', 'Invalid or expired credentials.');
    }
    const [profile, session] = await Promise.all([
      db.doc(`users/${decoded.uid}`).get(),
      db.doc(`access_sessions/${hash(token)}`).get(),
    ]);
    if (
      !profile.exists ||
      !session.exists ||
      session.data().uid !== decoded.uid ||
      session.data().expires_at < Date.now()
    )
      fail(401, 'UNAUTHORIZED', 'Invalid or expired session.');
    req.actor = { kind: 'user', uid: decoded.uid, ...profile.data() };
  }
  next();
}
export function user(req, write = false, admin = false) {
  const actor = req.actor;
  if (
    actor.kind !== 'user' ||
    (write && actor.role === 'viewer') ||
    (admin && actor.role !== 'admin')
  )
    fail(403, 'FORBIDDEN', 'Not permitted.');
  return actor;
}
export async function device(req, write = false, deviceOnly = false) {
  const id = req.params.device_id;
  if (!/^[A-Za-z0-9._-]{1,100}$/.test(id)) fail(404, 'NOT_FOUND', 'Device not found.');
  const ref = db.doc(`devices/${id}`),
    snap = await ref.get(),
    data = snap.data();
  const a = req.actor;
  if (!snap.exists || (a.kind === 'device' ? a.device_id !== id : data.owner !== a.uid))
    fail(404, 'NOT_FOUND', 'Device not found.');
  if (data.revoked) fail(403, 'REVOKED', 'Device credential revoked.');
  if (deviceOnly && a.kind !== 'device')
    fail(403, 'DEVICE_REQUIRED', 'Device credential required.');
  if (write && a.kind === 'user') user(req, true);
  return { ref, data, id };
}
export async function rateLimit(key, limit, seconds = 60) {
  const bucket = Math.floor(Date.now() / (seconds * 1000));
  const ref = db.doc(`rate_limits/${hash(key)}`);
  await db.runTransaction(async (tx) => {
    const snap = await tx.get(ref),
      prior = snap.data();
    const count = prior?.bucket === bucket ? prior.count : 0;
    if (count >= limit) fail(429, 'RATE_LIMIT', 'Too many requests; retry later.');
    tx.set(ref, { bucket, count: count + 1 });
  });
}
