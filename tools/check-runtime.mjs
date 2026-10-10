// Smoke-test the real local Functions/Hosting wrapper, not only the Express handler.
import {readFile} from 'node:fs/promises';
import {randomUUID,createHash} from 'node:crypto';
import assert from 'node:assert/strict';
const hash=s=>createHash('sha256').update(s).digest('hex');
const base='http://127.0.0.1:5000/api/v1';
const account=JSON.parse(await readFile('.local/admin.json','utf8'));
let session,device,key;
const serial='runtime-check-'+randomUUID();
async function call(path,method='GET',body,token=session?.access_token,headers={}) {
  const response=await fetch(base+path,{method,headers:{...(token?{Authorization:`Bearer ${token}`} : {}),
    ...(body?{'Content-Type':'application/json'}:{}),...headers},
    body:Buffer.isBuffer(body)?body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(30000)});
  assert.ok(response.ok,`${method} ${path}: HTTP ${response.status}`);
  if(response.status===204)return null;
  return response.headers.get('Content-Type')?.startsWith('image/')?response:response.json();
}
try {
  session=await call('/auth/login','POST',account);
  device=await call('/devices','POST',{device_name:'Temporary runtime check',device_type:'ESP32',location:'Software test'});
  const provision=await call('/device/register','POST',{device_id:device.device_id,serial_number:serial,hardware:'test',firmware:'test'});
  key=provision.device_key;const path=`/devices/${device.device_id}`;
  const result=await call(path+'/telemetry','POST',{voltage:null,current:null,power:null,temperature:null,timestamp:null,
    sample_id:'runtime:1',synthetic:true},key);assert.equal(result.accepted,true);
  const frame=Buffer.alloc(230454);frame.write('BM');frame.writeUInt32LE(frame.length,2);frame.writeUInt32LE(54,10);frame.writeUInt32LE(40,14);
  frame.writeInt32LE(320,18);frame.writeInt32LE(-240,22);frame.writeUInt16LE(1,26);frame.writeUInt16LE(24,28);frame.writeUInt32LE(230400,34);
  await call(path+'/fusion/frame','POST',frame,key,{'Content-Type':'image/bmp','X-Fusion-Sequence':'1','X-Synthetic':'true','X-Capture-Age-Ms':'100'});
  const download=await call(path+'/fusion/frame');assert.equal((await download.arrayBuffer()).byteLength,frame.length);
  const queued=await call(path+'/commands','POST',{command:'REQUEST_STATUS'});
  const pending=await call(path+'/commands','GET',undefined,key);assert.equal(pending.commands[0].command_id,queued.command_id);
  await call(path+`/commands/${queued.command_id}/ack`,'POST',{status:'success',detail:'Simulated device acknowledgement'},key);
  console.log('Runtime smoke test passed: Hosting → Functions → Auth/Firestore, telemetry, BMP upload/read and command acknowledgement.');
} finally {
  // Remove only this test's records, using fixed local emulator endpoints.
  process.env.GCLOUD_PROJECT='demo-smartdb';process.env.FIREBASE_AUTH_EMULATOR_HOST='127.0.0.1:9099';process.env.FIRESTORE_EMULATOR_HOST='127.0.0.1:8080';
  const {db}=await import('../cloud/src/firebase.js');
  if(device)await db.recursiveDelete(db.doc(`devices/${device.device_id}`));
  if(key)await db.doc(`device_keys/${hash(key)}`).delete();
  await db.doc(`serial_numbers/${hash(serial)}`).delete();
  if(session)await call('/auth/logout','POST',{refresh_token:session.refresh_token});
  await db.terminate();
}
