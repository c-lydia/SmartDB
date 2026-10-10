import {parseArgs} from 'node:util';
const {values}=parseArgs({options:{project:{type:'string'},email:{type:'string'},name:{type:'string'},role:{type:'string'}}});
if(!/^[a-z][a-z0-9-]{4,62}$/.test(values.project || '') || !values.email || !values.name || !['admin','operator','viewer'].includes(values.role)) {
  throw new Error('Usage: node cloud/scripts/provision-user.mjs --project PROJECT_ID --email EMAIL --name NAME --role admin|operator|viewer');
}
process.env.GCLOUD_PROJECT=values.project;
const {auth,db}=await import('../src/firebase.js');
const {createProfile}=await import('../src/security.js');
// The account must already exist in Firebase Auth. ADC authorizes this administrative operation.
const record=await auth.getUserByEmail(values.email);
const profile=await createProfile(record.uid,record.email,values.name,values.role);
if(profile.role!==values.role)throw new Error('An existing profile has a different role. Review it explicitly in Firestore; this command does not change roles.');
console.log(`Account profile ready: ${profile.email} (${profile.role}), UID ${record.uid}`);
await db.terminate();
