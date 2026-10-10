import express from 'express';
import {randomUUID} from 'node:crypto';
import {db} from './firebase.js';
import {schemas, telemetry, control} from './schemas.js';
import {ApiError, authenticate, device, fail, hash, login, logout, nextId, now, rateLimit, refresh, secret, user} from './security.js';

export const app = express();
app.disable('x-powered-by');
app.use((req, res, next) => {
  req.requestId = randomUUID(); res.set('Cache-Control', 'no-store');
  res.set('X-Content-Type-Options', 'nosniff'); next();
});
// Separate team frontends may opt into browser access; bearer authorization is still required.
app.use((req,res,next)=>{
  const origin=req.get('Origin'), allowed=(process.env.SMARTDB_ALLOWED_ORIGINS || '').split(',').map(x=>x.trim()).filter(Boolean);
  if(origin && allowed.includes(origin)) {
    res.set('Access-Control-Allow-Origin',origin);res.vary('Origin');
    res.set('Access-Control-Allow-Methods','GET,POST,PUT,PATCH,OPTIONS');
    res.set('Access-Control-Allow-Headers','Authorization,Content-Type,X-Fusion-Sequence,X-Synthetic,X-Capture-Age-Ms');
    res.set('Access-Control-Expose-Headers','X-Received-At,X-Fusion-Sequence,X-Synthetic,X-Capture-Age-Ms');
  }
  if(req.method==='OPTIONS')return res.sendStatus(origin && allowed.includes(origin)?204:403);
  next();
});
app.use(express.json({limit: '32kb', strict: true}));
const api = express.Router();
app.use('/api/v1', api);
const body = (req, schema) => schema.parse(req.body);
const publicUser = a => ({id: a.id, email: a.email, name: a.name, role: a.role});
const publicDevice = (id, d) => ({device_id: id, device_name: d.device_name, device_type: 'ESP32', location: d.location,
  status: d.revoked ? 'revoked' : !d.last_seen ? 'registered' : Date.now()-Date.parse(d.last_seen) < 180000 ? 'online' : 'offline'});

api.post('/auth/login', async (req, res) => {
  const data = body(req, schemas.login);
  await rateLimit(`login:${hash(data.email.toLowerCase())}`, 10);
  res.json(await login(data));
});
api.post('/auth/refresh', async (req, res) => {
  const data = body(req, schemas.refresh);
  await rateLimit(`refresh:${hash(data.refresh_token)}`, 10);
  res.json(await refresh(data.refresh_token));
});
api.use(authenticate);
api.use(async (req, res, next) => {
  await rateLimit(`actor:${req.actor.uid || req.actor.device_id}`, 240); next();
});
api.post('/auth/logout', async (req, res) => {
  const actor = user(req); await logout(actor.uid, body(req, schemas.refresh).refresh_token); res.sendStatus(204);
});
api.get('/users', async (req, res) => {
  user(req, false, true); res.json((await db.collection('users').limit(500).get()).docs.map(d => publicUser(d.data())));
});
api.get('/users/me', (req, res) => res.json(publicUser(user(req))));
api.patch('/users/me', async (req, res) => {
  const actor = user(req), data = body(req, schemas.profile);
  await db.doc(`users/${actor.uid}`).update(data); res.json({...publicUser(actor), ...data});
});
api.get('/users/me/notification-settings', (req, res) => {
  user(req); res.json({push: false, email: false, sms: false});
});
api.get('/devices', async (req, res) => {
  const a = user(req);
  res.json((await db.collection('devices').where('owner','==',a.uid).limit(500).get()).docs.map(d => publicDevice(d.id,d.data())));
});
api.post('/devices', async (req, res) => {
  const a = user(req, true), data = body(req, schemas.device), ref = db.collection('devices').doc();
  const record = {...data, owner: a.uid, created_at: now(), last_seen: null, firmware: '', revoked: false,
    desired_config: {max_temperature: 60, max_current: .8, sampling_rate: 5}};
  await ref.create(record); res.status(201).json(publicDevice(ref.id, record));
});
api.post('/device/register', async (req, res) => {
  const a = user(req, true, true), data = body(req, schemas.provision);
  const ref = db.doc(`devices/${data.device_id || 'esp32-'+hash(data.serial_number).slice(0,20)}`);
  const serialRef = db.doc(`serial_numbers/${hash(data.serial_number)}`);
  const key = 'sdb_device_' + secret();
  await db.runTransaction(async tx => {
    const [snap, serial] = await Promise.all([tx.get(ref), tx.get(serialRef)]);
    if (snap.exists && snap.data().owner !== a.uid) fail(404,'NOT_FOUND','Device not found.');
    if (serial.exists || snap.data()?.credential_hash) fail(409,'ALREADY_PROVISIONED','Device already provisioned.');
    const record = snap.data() || {owner: a.uid, device_name: data.serial_number, device_type: 'ESP32', location: 'Unassigned',
      created_at: now(), last_seen: null, revoked: false, desired_config: {max_temperature:60,max_current:.8,sampling_rate:5}};
    tx.set(ref, {...record, hardware: data.hardware, firmware: data.firmware, credential_hash: hash(key)});
    tx.create(serialRef, {device_id: ref.id}); tx.create(db.doc(`device_keys/${hash(key)}`), {device_id: ref.id});
  });
  res.status(201).json({device_id: ref.id, device_key: key});
});
api.get('/devices/:device_id', async (req, res) => { const d = await device(req); res.json(publicDevice(d.id,d.data)); });
api.post('/devices/:device_id/credential/rotate', async (req,res) => {
  user(req,true,true); const d=await device(req,true), key='sdb_device_'+secret();
  await db.runTransaction(async tx=>{
    const current=(await tx.get(d.ref)).data();
    if(!current.credential_hash)fail(409,'NOT_PROVISIONED','Provision the board before rotating its credential.');
    tx.delete(db.doc(`device_keys/${current.credential_hash}`));
    tx.create(db.doc(`device_keys/${hash(key)}`),{device_id:d.id});
    tx.update(d.ref,{credential_hash:hash(key)});
  });res.status(201).json({device_id:d.id,device_key:key});
});
api.get('/devices/:device_id/status', async (req, res) => {
  const d = await device(req); res.json({online: publicDevice(d.id,d.data).status === 'online',
    last_seen: d.data.last_seen, firmware: d.data.firmware || '', config_version: d.data.latest?.config_version ?? null});
});
api.post('/devices/:device_id/heartbeat', async (req,res) => {
  const d = await device(req,true), data = body(req,schemas.heartbeat);
  await d.ref.update({last_seen:now(),heartbeat:data}); res.status(202).json({accepted:true});
});
api.post('/devices/:device_id/sync', async (req,res) => {
  const d = await device(req,true), data = body(req,schemas.sync);
  // A diagnostic time range is advisory; only individual accepted samples are durable.
  const end = now(), missing = Date.parse(data.last_timestamp) < Date.now()-10000;
  res.json(missing ? {missing_data:true,upload_from:data.last_timestamp,upload_to:end} : {missing_data:false});
});
api.get('/devices/:device_id/config', async (req,res) => {
  const d = await device(req); res.json(d.data.desired_config);
});

async function queueCommand(d, value) {
  return db.runTransaction(async tx => {
    const id = await nextId(tx, 'commands');
    const record = {...value,command_id:id.value,status:'queued',created_at:now(),expires_at:Date.now()+120000};
    tx.set(id.ref,{value:id.value}); tx.create(d.ref.collection('commands').doc(String(id.value)),record);
    if (value.command === 'APPLY_CONFIG') tx.update(d.ref,{desired_config:value.value});
    if (value.command === 'SET_INTERVAL') tx.update(d.ref,{'desired_config.sampling_rate':value.value});
    return record;
  });
}
async function commands(d, pending = false) {
  const rows = (await d.ref.collection('commands').orderBy('command_id','desc').limit(100).get()).docs;
  const result = [];
  for (const row of rows) {
    let value = row.data();
    if (value.status === 'queued' && value.expires_at < Date.now()) {
      // Conditional update prevents overwriting a concurrent acknowledgement.
      value = await db.runTransaction(async tx => {
        const latest = (await tx.get(row.ref)).data();
        if (latest.status === 'queued' && latest.expires_at < Date.now()) {
          latest.status='expired'; tx.update(row.ref,{status:'expired'});
        }
        return latest;
      });
    }
    if (!pending || value.status === 'queued') result.push(value);
  }
  return pending ? result.sort((a,b)=>a.command_id-b.command_id).slice(0,1) : result;
}
api.put('/devices/:device_id/config', async (req,res) => {
  user(req,true); const d=await device(req,true), value=body(req,control);
  await queueCommand(d,{command:'APPLY_CONFIG',value}); res.json(value);
});
api.post('/devices/:device_id/commands', async (req,res) => {
  user(req,true); const d=await device(req,true), value=body(req,schemas.command);
  const command=await queueCommand(d,value); res.status(202).json({command_id:command.command_id,status:'queued'});
});
api.get('/devices/:device_id/commands', async (req,res) => {
  const d=await device(req); res.json({commands:await commands(d,req.actor.kind === 'device')});
});
api.post('/devices/:device_id/commands/:command_id/ack', async (req,res) => {
  const d=await device(req,true,true), value=body(req,schemas.ack);
  if (!/^\d{1,15}$/.test(req.params.command_id)) fail(404,'NOT_FOUND','Command not found.');
  const ref=d.ref.collection('commands').doc(req.params.command_id);
  await db.runTransaction(async tx => {
    const snap=await tx.get(ref);
    if (!snap.exists) fail(404,'NOT_FOUND','Command not found.');
    const prior=snap.data();
    if (prior.status === value.status && (prior.detail || '') === (value.detail || '')) return;
    if (prior.status !== 'queued') fail(409,'CONFLICT','Command is no longer queued.');
    tx.update(ref,{...value,acknowledged_at:now()});
  });
  res.sendStatus(204);
});

api.post('/devices/:device_id/telemetry', async (req,res) => {
  const d=await device(req,true), value=body(req,telemetry), digest=hash(JSON.stringify(value));
  const ref=d.ref.collection('samples').doc(value.sample_id ? hash(value.sample_id) : randomUUID());
  const duplicate=await db.runTransaction(async tx => {
    const [prior, current] = await Promise.all([tx.get(ref),tx.get(d.ref)]);
    if (prior.exists) {
      if (prior.data().digest !== digest) fail(409,'SAMPLE_CONFLICT','Sample identifier was reused with different content.');
      tx.update(d.ref,{last_seen:now()}); return true;
    }
    const trip = !value.synthetic && value.protection_state === 'tripped' &&
      (current.data().latest?.protection_state !== 'tripped' || current.data().latest?.protection_reason !== value.protection_reason);
    const id=trip ? await nextId(tx,'alerts') : null;
    const received_at=now();
    tx.create(ref,{payload:value,digest,received_at}); tx.update(d.ref,{last_seen:received_at,latest:value});
    if (trip) {
      const message=`Local protection tripped: ${value.protection_reason || 'unspecified'}`;
      tx.set(id.ref,{value:id.value});
      tx.create(db.doc(`alerts/${id.value}`),{id:id.value,owner:d.data.owner,device_id:d.id,type:'protection_trip',severity:'critical',message,status:'active',created_at:received_at});
      tx.create(db.doc(`notifications/${id.value}`),{id:id.value,owner:d.data.owner,title:message,read:false});
    }
    return false;
  });
  // Commands are delivered only to device credentials, never operator diagnostic uploads.
  const pending=req.actor.kind === 'device' ? await commands(d,true) : [];
  res.status(202).json({accepted:true,duplicate,command:pending[0] || null});
});
api.get('/devices/:device_id/telemetry/latest', async (req,res) => {
  const d=await device(req); if (!d.data.latest) fail(404,'NOT_FOUND','No telemetry received yet.'); res.json(d.data.latest);
});
api.get('/devices/:device_id/telemetry', async (req,res) => {
  const d=await device(req), limit=req.query.limit === undefined ? 100 : Number(req.query.limit);
  if (!Number.isInteger(limit) || limit<1 || limit>1000) fail(400,'INVALID_QUERY','Limit must be 1–1000.');
  let query=d.ref.collection('samples').orderBy('received_at','desc');
  for (const [key,op] of [['from','>='],['to','<=']]) {
    if (req.query[key]) {
      const parsed=Date.parse(req.query[key]);
      if (!Number.isFinite(parsed)) fail(400,'INVALID_QUERY','Use an ISO timestamp.');
      query=query.where('received_at',op,new Date(parsed).toISOString());
    }
  }
  res.json((await query.limit(limit).get()).docs.map(x=>x.data().payload));
});

// One bounded, uncompressed QVGA preview per board. No arbitrary file storage.
api.post('/devices/:device_id/fusion/frame',express.raw({type:'image/bmp',limit:'240kb'}),async(req,res)=>{
  const d=await device(req,true,true), bytes=req.body;
  if(!Buffer.isBuffer(bytes) || bytes.length!==230454 || bytes.toString('ascii',0,2)!=='BM' ||
    bytes.readUInt32LE(2)!==230454 || bytes.readUInt32LE(10)!==54 || bytes.readUInt32LE(14)!==40 ||
    bytes.readInt32LE(18)!==320 || bytes.readInt32LE(22)!==-240 || bytes.readUInt16LE(26)!==1 ||
    bytes.readUInt16LE(28)!==24 || bytes.readUInt32LE(30)!==0 || bytes.readUInt32LE(34)!==230400)
    fail(400,'INVALID_FRAME','Expected a 320 × 240 top-down 24-bit SmartDB BMP.');
  const sequence=Number(req.get('X-Fusion-Sequence')), synthetic=req.get('X-Synthetic');
  const age=Number(req.get('X-Capture-Age-Ms'));
  if(!req.get('X-Fusion-Sequence') || !Number.isSafeInteger(sequence)||sequence<0 || !['true','false'].includes(synthetic) ||
    !req.get('X-Capture-Age-Ms') || !Number.isSafeInteger(age)||age<0||age>2000)
    fail(400,'INVALID_FRAME','Frame metadata is missing or stale.');
  await rateLimit(`frame:${d.id}`,6);
  await d.ref.collection('frames').doc('latest').set({bytes,sequence,synthetic:synthetic==='true',capture_age_ms:age,received_at:now()});
  res.status(202).json({accepted:true});
});
api.get('/devices/:device_id/fusion/frame',async(req,res)=>{
  const d=await device(req), frame=(await d.ref.collection('frames').doc('latest').get()).data();
  if(!frame)fail(404,'NOT_FOUND','No fused preview received.');
  res.set({'Content-Type':'image/bmp','X-Fusion-Sequence':String(frame.sequence),'X-Synthetic':String(frame.synthetic),
    'X-Capture-Age-Ms':String(frame.capture_age_ms),'X-Received-At':frame.received_at});
  res.send(Buffer.from(frame.bytes));
});
api.get('/alerts', async (req,res) => {
  const a=user(req); const docs=await db.collection('alerts').where('owner','==',a.uid).limit(500).get();
  res.json(docs.docs.map(d=>{const {owner,...item}=d.data();return item;}).sort((a,b)=>b.id-a.id));
});
api.post('/alerts', async (req,res) => {
  const a=user(req,true), data=body(req,schemas.alert); req.params.device_id=data.device_id; await device(req,true);
  const value=await db.runTransaction(async tx=>{
    const id=await nextId(tx,'alerts'), row={...data,id:id.value,status:'active',created_at:now()};
    tx.set(id.ref,{value:id.value});tx.create(db.doc(`alerts/${id.value}`),{...row,owner:a.uid});
    tx.create(db.doc(`notifications/${id.value}`),{id:id.value,owner:a.uid,title:data.message,read:false}); return row;
  });res.status(201).json(value);
});
async function ownedItem(req,collection,key) {
  const a=user(req), id=req.params[key];
  if (!/^\d{1,15}$/.test(id)) fail(404,'NOT_FOUND','Record not found.');
  const ref=db.doc(`${collection}/${id}`), snap=await ref.get();
  if (!snap.exists || snap.data().owner!==a.uid) fail(404,'NOT_FOUND','Record not found.');
  return {ref,data:snap.data()};
}
api.put('/alerts/:alert_id/resolve', async (req,res)=>{
  user(req,true); const record=await ownedItem(req,'alerts','alert_id'), data=schemas.resolve.parse(req.body || {});
  const change={status:'resolved',resolved_at:now(),resolution:data.message || ''}; await record.ref.update(change);
  const {owner,...result}={...record.data,...change};res.json(result);
});
api.get('/notifications',async (req,res)=>{
  const a=user(req), docs=await db.collection('notifications').where('owner','==',a.uid).limit(500).get();
  res.json(docs.docs.map(d=>{const {owner,...item}=d.data();return item;}).sort((a,b)=>b.id-a.id));
});
api.patch('/notifications/:notification_id/read',async (req,res)=>{
  const record=await ownedItem(req,'notifications','notification_id'), data=body(req,schemas.read);
  await record.ref.update(data);const {owner,...result}={...record.data,...data};res.json(result);
});
api.use((req,res)=>res.status(404).json({code:'NOT_FOUND',message:'Endpoint not found.'}));
app.use((error,req,res,next)=>{
  const validation=error.name==='ZodError' || error.type==='entity.parse.failed';
  const status=validation ? 400 : error.type==='entity.too.large' ? 413 : error instanceof ApiError ? error.status : 500;
  if (status===500) console.error('API error',req.requestId,error.code || error.name);
  if (status===429) res.set('Retry-After','60');
  res.status(status).json({code:validation?'INVALID_REQUEST':error.code || 'INTERNAL_ERROR',
    message:validation?'Request fields are invalid.':status===500?'Request could not be completed.':error.message,request_id:req.requestId});
});
