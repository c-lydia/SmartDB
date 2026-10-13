import { test, before, after } from 'node:test';
import assert from 'node:assert/strict';
import request from 'supertest';
import { auth, db, projectId } from '../src/firebase.js';
import { app } from '../src/app.js';
import { createProfile } from '../src/security.js';
if (!projectId.startsWith('demo-'))
  throw new Error('Tests only run against a demo emulator project.');
let admin, other, viewer, deviceId, key;
const password = 'Integration-Test-Password-482!';
async function account(email, role) {
  const user = await auth.createUser({ email, password });
  await createProfile(user.uid, email, email, role);
  const result = await request(app)
    .post('/api/v1/auth/login')
    .send({ email, password })
    .expect(200);
  return { ...result.body, uid: user.uid, email };
}
const get = (path, token = admin.access_token) =>
  request(app)
    .get('/api/v1' + path)
    .auth(token, { type: 'bearer' });
const post = (path, body, token = admin.access_token) =>
  request(app)
    .post('/api/v1' + path)
    .auth(token, { type: 'bearer' })
    .send(body);
const sample = (id = 'boot:1') => ({
  sample_id: id,
  voltage: null,
  power: null,
  current: 0.42,
  temperature: 34,
  timestamp: null,
  time_quality: 'unknown',
  synthetic: false,
  relay_state: 'open',
  protection_state: 'disarmed',
  protection_reason: 'manual',
  config_version: 1,
  commissioned: false,
  storage_ok: true,
  current_sensor: 'SCT-013-000',
  arc_detection_available: false,
  events: [],
});
before(async () => {
  await fetch(
    `http://${process.env.FIRESTORE_EMULATOR_HOST}/emulator/v1/projects/${projectId}/databases/(default)/documents`,
    { method: 'DELETE' },
  );
  await fetch(
    `http://${process.env.FIREBASE_AUTH_EMULATOR_HOST}/emulator/v1/projects/${projectId}/accounts`,
    { method: 'DELETE' },
  );
  admin = await account('owner@example.test', 'admin');
  other = await account('other@example.test', 'admin');
  viewer = await account('viewer@example.test', 'viewer');
});
after(async () => {
  await db.terminate();
});
test('login failure, missing bearer, and viewer writes are denied', async () => {
  await request(app)
    .post('/api/v1/auth/login')
    .send({ email: admin.email, password: 'wrong-password' })
    .expect(401);
  await request(app).get('/api/v1/devices').expect(401);
  await post(
    '/devices',
    { device_name: 'No', device_type: 'ESP32', location: 'Bench' },
    viewer.access_token,
  ).expect(403);
  await get('/users', viewer.access_token).expect(403);
});
test('browser origins are explicitly allowed without bypassing authentication', async () => {
  process.env.SMARTDB_ALLOWED_ORIGINS = 'https://team.example.test';
  const allowed = await request(app)
    .options('/api/v1/devices')
    .set('Origin', 'https://team.example.test')
    .expect(204);
  assert.equal(allowed.headers['access-control-allow-origin'], 'https://team.example.test');
  await request(app)
    .options('/api/v1/devices')
    .set('Origin', 'https://untrusted.example.test')
    .expect(403);
  await request(app).get('/api/v1/devices').set('Origin', 'https://team.example.test').expect(401);
  delete process.env.SMARTDB_ALLOWED_ORIGINS;
});
test('device registration, one-time credential and owner isolation', async () => {
  const d = await post('/devices', {
    device_name: 'Bench',
    device_type: 'ESP32',
    location: 'Lab',
  }).expect(201);
  deviceId = d.body.device_id;
  const credential = await post('/device/register', {
    device_id: deviceId,
    serial_number: 'board-001',
    hardware: 'v2',
    firmware: 'test',
  }).expect(201);
  key = credential.body.device_key;
  assert.ok(key.startsWith('sdb_device_'));
  await post('/device/register', {
    device_id: deviceId,
    serial_number: 'board-001',
    hardware: 'v2',
    firmware: 'test',
  }).expect(409);
  await get(`/devices/${deviceId}`, other.access_token).expect(404);
  const own = await get(`/devices/${deviceId}`).expect(200);
  assert.equal(own.body.device_key, undefined);
  assert.equal(own.body.credential_hash, undefined);
  await get('/users', key).expect(403);
});
test('telemetry persists, deduplicates concurrent retries, rejects conflicting IDs and malformed values', async () => {
  const endpoint = `/devices/${deviceId}/telemetry`;
  await Promise.all([
    post(endpoint, sample(), key).expect(202),
    post(endpoint, sample(), key).expect(202),
  ]);
  let history = await get(endpoint).expect(200);
  assert.equal(history.body.length, 1);
  assert.equal(history.body[0].voltage, null);
  await post(endpoint, { ...sample(), current: 0.43 }, key).expect(409);
  await post(endpoint, { ...sample('bad'), current: -1 }, key).expect(400);
  await post(endpoint, { ...sample('bad2'), arc_detection_available: true }, key).expect(400);
  await get(endpoint + '?limit=5000').expect(400);
  await get(endpoint, other.access_token).expect(404);
  const latest = await get(endpoint + '/latest').expect(200);
  assert.equal(latest.body.current, 0.42);
});
test('a device credential cannot upload to another device', async () => {
  const otherDevice = await post(
    '/devices',
    { device_name: 'Other', device_type: 'ESP32', location: 'Other lab' },
    other.access_token,
  ).expect(201);
  await post(`/devices/${otherDevice.body.device_id}/telemetry`, sample(), key).expect(404);
});
test('trip alerts and notifications are durable and not duplicated by retries', async () => {
  const value = {
    ...sample('boot:2'),
    protection_state: 'tripped',
    protection_reason: 'overcurrent',
  };
  await post(`/devices/${deviceId}/telemetry`, value, key).expect(202);
  await post(`/devices/${deviceId}/telemetry`, value, key).expect(202);
  const alerts = await get('/alerts').expect(200);
  assert.equal(alerts.body.length, 1);
  const id = alerts.body[0].id;
  assert.equal(alerts.body[0].severity, 'critical');
  await request(app)
    .put(`/api/v1/alerts/${id}/resolve`)
    .auth(other.access_token, { type: 'bearer' })
    .send({})
    .expect(404);
  await request(app)
    .put(`/api/v1/alerts/${id}/resolve`)
    .auth(admin.access_token, { type: 'bearer' })
    .send({ message: 'Checked' })
    .expect(200);
  const notes = await get('/notifications').expect(200);
  assert.equal(notes.body.length, 1);
  await request(app)
    .patch(`/api/v1/notifications/${id}/read`)
    .auth(admin.access_token, { type: 'bearer' })
    .send({ read: true })
    .expect(200);
});
test('commands require owner permission, have no re-arm, and require device acknowledgement', async () => {
  const endpoint = `/devices/${deviceId}/commands`;
  await post(endpoint, { command: 'CLOSE_RELAY' }).expect(400);
  await post(endpoint, { command: 'OPEN_RELAY' }, other.access_token).expect(404);
  const command = await post(endpoint, { command: 'OPEN_RELAY' }).expect(202);
  const upload = await post(`/devices/${deviceId}/telemetry`, sample('boot:3'), key).expect(202);
  assert.equal(upload.body.command.command_id, command.body.command_id);
  const ack = endpoint + `/${command.body.command_id}/ack`;
  await post(ack, { status: 'success' }).expect(403);
  await post(ack, { status: 'success' }, key).expect(204);
  await post(ack, { status: 'success' }, key).expect(204);
  const queue = await get(endpoint, key).expect(200);
  assert.equal(queue.body.commands.length, 0);
});
test('configuration uses bench bounds and queues application', async () => {
  const endpoint = `/api/v1/devices/${deviceId}/config`;
  await request(app)
    .put(endpoint)
    .auth(admin.access_token, { type: 'bearer' })
    .send({ max_current: 2, max_temperature: 60, sampling_rate: 5 })
    .expect(400);
  await request(app)
    .put(endpoint)
    .auth(admin.access_token, { type: 'bearer' })
    .send({ max_current: 0.7, max_temperature: 55, sampling_rate: 10 })
    .expect(200);
  const result = await get(`/devices/${deviceId}/commands`, key).expect(200);
  assert.equal(result.body.commands[0].command, 'APPLY_CONFIG');
  assert.equal(result.body.commands[0].value.max_current, 0.7);
});
test('refresh rotates once and logout revokes the session', async () => {
  const initial = await account('rotate@example.test', 'operator');
  const rotated = await post('/auth/refresh', { refresh_token: initial.refresh_token }).expect(200);
  assert.notEqual(rotated.body.refresh_token, initial.refresh_token);
  await post('/auth/refresh', { refresh_token: initial.refresh_token }).expect(401);
  await get('/users/me', rotated.body.access_token).expect(200);
  await post(
    '/auth/logout',
    { refresh_token: rotated.body.refresh_token },
    rotated.body.access_token,
  ).expect(204);
  await get('/users/me', rotated.body.access_token).expect(401);
});
test('only the paired device can upload bounded fresh BMP previews; reads stay owner scoped', async () => {
  const endpoint = `/devices/${deviceId}/fusion/frame`,
    bytes = Buffer.alloc(230454);
  bytes.write('BM');
  bytes.writeUInt32LE(bytes.length, 2);
  bytes.writeUInt32LE(54, 10);
  bytes.writeUInt32LE(40, 14);
  bytes.writeInt32LE(320, 18);
  bytes.writeInt32LE(-240, 22);
  bytes.writeUInt16LE(1, 26);
  bytes.writeUInt16LE(24, 28);
  bytes.writeUInt32LE(230400, 34);
  const upload = (payload, token = key, age = 100) =>
    request(app)
      .post('/api/v1' + endpoint)
      .auth(token, { type: 'bearer' })
      .set('Content-Type', 'image/bmp')
      .set('X-Fusion-Sequence', '7')
      .set('X-Synthetic', 'true')
      .set('X-Capture-Age-Ms', String(age))
      .send(payload);
  await get(endpoint).expect(404);
  await upload(bytes, admin.access_token).expect(403);
  await upload(Buffer.from('not a picture')).expect(400);
  await upload(bytes, key, 2001).expect(400);
  await upload(Buffer.alloc(300000)).expect(413);
  await upload(bytes).expect(202);
  const frame = await get(endpoint).expect(200);
  assert.equal(frame.headers['content-type'], 'image/bmp');
  assert.equal(frame.headers['x-synthetic'], 'true');
  assert.equal(frame.headers['x-fusion-sequence'], '7');
  assert.equal(frame.body.length, bytes.length);
  await get(endpoint, other.access_token).expect(404);
});
test('expired commands are withheld and cannot overwrite an acknowledged result', async () => {
  const endpoint = `/devices/${deviceId}/commands`,
    command = await post(endpoint, { command: 'REQUEST_STATUS' }).expect(202);
  await db
    .doc(`devices/${deviceId}/commands/${command.body.command_id}`)
    .update({ expires_at: Date.now() - 1 });
  const result = await get(endpoint, key).expect(200);
  assert.ok(!result.body.commands.some((c) => c.command_id === command.body.command_id));
  await post(endpoint + `/${command.body.command_id}/ack`, { status: 'success' }, key).expect(409);
});
test('credential rotation immediately invalidates the old key and is owner-admin only', async () => {
  const endpoint = `/devices/${deviceId}/credential/rotate`;
  await post(endpoint, {}, other.access_token).expect(404);
  await post(endpoint, {}, key).expect(403);
  const result = await post(endpoint, {}).expect(201);
  await get(`/devices/${deviceId}`, key).expect(401);
  key = result.body.device_key;
  await get(`/devices/${deviceId}`, key).expect(200);
});
