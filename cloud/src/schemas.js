import {z} from 'zod';
const number = z.number().finite();
const nullable = number.nullable();
const text = z.string().trim().min(1).max(200);
export const deviceId = z.string().regex(/^[A-Za-z0-9._-]{1,100}$/);
export const control = z.object({
  max_temperature: number.min(20).max(100),
  max_current: number.gt(0).max(1),
  sampling_rate: z.number().int().min(5).max(60),
}).strict();
const region = z.object({id: text, supported: z.boolean(), ambiguous: z.boolean(),
  samples: z.number().int().min(0).max(768), boundary_samples: z.number().int().min(0).max(768),
  max_c: nullable, mean_c: nullable, rise_c_per_min: nullable}).strict();
export const vision = z.object({ready: z.boolean(), synthetic: z.boolean(), reason: z.string().max(256),
  installation_id: text, camera_id: text, camera_frame_id: z.string().max(128),
  calibration_version: text, sequence: z.number().int().nonnegative(), display_min_c: number,
  display_max_c: number, regions: z.array(region).max(8)}).strict();
const event = z.object({sequence: z.number().int().nonnegative(), boot_id: z.number().int().nonnegative(),
  uptime_ms: z.number().int().nonnegative(), state: z.enum(['disarmed','armed','tripped']),
  reason: z.string().max(128), current_a: number.nonnegative().nullable(), temperature_c: nullable}).strict();
export const telemetry = z.object({
  voltage: nullable, current: number.nonnegative().nullable(), power: nullable, temperature: nullable,
  timestamp: z.iso.datetime({offset: true}).nullable(),
  sample_id: z.string().min(1).max(100).optional(), uptime_ms: z.number().int().nonnegative().optional(),
  time_quality: z.enum(['synced','unknown']).optional(), synthetic: z.boolean().optional(),
  relay_state: z.enum(['open','closed']).optional(), protection_state: z.enum(['disarmed','armed','tripped']).optional(),
  protection_reason: z.string().max(128).optional(), config_version: z.number().int().positive().optional(),
  commissioned: z.boolean().optional(), storage_ok: z.boolean().optional(), current_sensor: z.string().max(128).optional(),
  arc_detection_available: z.literal(false).optional(), events: z.array(event).max(16).optional(), vision: vision.optional(),
}).strict();
export const schemas = {
  login: z.object({email: z.email().max(254), password: z.string().min(8).max(256)}).strict(),
  refresh: z.object({refresh_token: z.string().min(20).max(4096)}).strict(),
  profile: z.object({name: z.string().trim().min(1).max(100)}).strict(),
  device: z.object({device_name: text, device_type: z.literal('ESP32'), location: text}).strict(),
  provision: z.object({serial_number: text, hardware: text, firmware: text, device_id: deviceId.optional()}).strict(),
  heartbeat: z.object({uptime: z.number().int().nonnegative(), wifi_rssi: z.number().int().min(-127).max(0)}).strict(),
  sync: z.object({last_timestamp: z.iso.datetime({offset: true})}).strict(),
  alert: z.object({device_id: deviceId, type: text, severity: z.enum(['low','medium','high','critical']), message: z.string().min(1).max(1000)}).strict(),
  resolve: z.object({message: z.string().max(1000).optional()}).strict(),
  read: z.object({read: z.boolean()}).strict(),
  command: z.discriminatedUnion('command', [
    z.object({command: z.literal('OPEN_RELAY')}).strict(),
    z.object({command: z.literal('REQUEST_STATUS')}).strict(),
    z.object({command: z.literal('SET_INTERVAL'), value: z.number().int().min(5).max(60)}).strict(),
  ]),
  ack: z.object({status: z.enum(['success','failed']), detail: z.string().max(256).optional()}).strict(),
};
