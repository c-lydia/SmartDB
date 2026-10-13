import { initializeApp, getApps } from 'firebase-admin/app';
import { getAuth } from 'firebase-admin/auth';
import { getFirestore } from 'firebase-admin/firestore';

const emulator = Boolean(process.env.FIREBASE_AUTH_EMULATOR_HOST);
if (emulator !== Boolean(process.env.FIRESTORE_EMULATOR_HOST)) {
  throw new Error('Auth and Firestore emulators must be configured together.');
}
export const projectId =
  process.env.GCLOUD_PROJECT || process.env.GOOGLE_CLOUD_PROJECT || 'demo-smartdb';
if (projectId.startsWith('demo-') && !emulator) {
  throw new Error('Demo projects require Auth and Firestore emulators.');
}
if (!getApps().length) initializeApp({ projectId });
export const db = getFirestore();
export const auth = getAuth();
export const isEmulator = emulator;
