import {onRequest} from 'firebase-functions/v2/https';
import {app} from './app.js';
export const api = onRequest({region: 'asia-southeast1', maxInstances: 5, timeoutSeconds: 30, cors: false}, app);
