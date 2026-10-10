import importlib.util
import io
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('setup_tool', Path(__file__).resolve().parents[1] / 'tools/setup.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


def profile():
    data = setup.defaults()
    data['settings'].update(wifi_ssid='Test network', wifi_password='test-passphrase')
    return data


class FakeSerial:
    def __init__(self, **kwargs):
        self.written = b''; self.lines = []; self.closed = False

    def open(self):
        assert self.dtr is False and self.rts is False

    def close(self):
        self.closed = True

    def write(self, value):
        self.written += value
        request = json.loads(value[len(b'SMARTDB '):])
        self.lines = [b'Boot log\n', b'SMARTDB {"id":"unrelated","ok":true}\n',
                      b'SMARTDB ' + json.dumps({'id': request['id'], 'ok': True, 'board': 'smartdb_s3', 'protocol': 1}).encode() + b'\n']

    def flush(self):
        pass

    def read_until(self, *args):
        return self.lines.pop(0) if self.lines else b''


class SetupTests(unittest.TestCase):
    def test_profile_persistence_and_permissions(self):
        data = profile()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.setup.json'
            setup.save_profile(data, path)
            self.assertEqual(setup.load_profile(path), data)
            if os.name == 'posix':
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(list(Path(directory).glob('*.tmp')), [])

    def test_invalid_profile_does_not_replace_existing(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.setup.json'; data = profile(); setup.save_profile(data, path)
            data['settings']['wifi_ssid'] = ''
            with self.assertRaises(ValueError):
                setup.save_profile(data, path)
            self.assertEqual(setup.load_profile(path)['settings']['wifi_ssid'], 'Test network')

    def test_invalid_connection_fields(self):
        for key, value in [('wifi_ssid', 'é' * 17), ('wifi_password', 'short'), ('api_token', 'x'*23),
                           ('camera_url', 'http://secret@camera/capture'), ('camera_url', 'http:///capture'),
                           ('telemetry_url', 'http://server/api'), ('camera_id', 'a\nb'),
                           ('api_token', 'x'*24+'\x1b'), ('camera_url', 'http://host:99999/capture')]:
            data = profile()['settings']; data[key] = value
            with self.subTest(field=key), self.assertRaises(ValueError):
                setup.validate_settings(data)

    def test_telemetry_optional_but_authenticated(self):
        settings = profile()['settings']; setup.validate_settings(settings)
        settings['telemetry_url'] = 'https://server.example/api/v1/devices/one/telemetry'
        with self.assertRaises(ValueError):
            setup.validate_settings(settings)
        settings['telemetry_token'] = 'test-token'; setup.validate_settings(settings)

    def test_serial_roundtrip_ignores_logs_and_wrong_ids(self):
        with setup.Device('fake', FakeSerial) as device:
            response = device.request('save_settings', profile()['settings'])
            self.assertTrue(response['ok'])
            self.assertIn(b'"op":"save_settings"', device.serial.written)
        self.assertTrue(device.serial.closed)

    def test_bad_serial_responses_are_ignored(self):
        for line in [b'noise\n', b'SMARTDB invalid\n', b'SMARTDB []\n', b'SMARTDB {"id":"wrong"}\n']:
            self.assertIsNone(setup.response_from_line(line, 'expected'))

    def test_wrong_board_is_rejected(self):
        with self.assertRaises(ValueError):
            setup.check_board({'protocol': 1, 'board': 'esp32cam'}, 'smartdb_s3')

    def test_protection_limits_and_versions(self):
        data = setup.control_config({'version': 5}, '.8', '60', '111.1111', False)
        self.assertEqual(data['version'], 6); self.assertFalse(data['commissioned'])
        for value in ['1.1', '0', 'nan', 'inf']:
            with self.assertRaises(ValueError):
                setup.control_config({'version': 5}, value, '60', '111', False)

    def test_secret_prompt_does_not_show_saved_value(self):
        with patch.object(setup.getpass, 'getpass', return_value='') as prompt:
            self.assertEqual(setup.ask('Password', 'test-secret', secret=True), 'test-secret')
            self.assertNotIn('test-secret', prompt.call_args.args[0])

    def test_platformio_receives_arguments_without_shell(self):
        with patch.object(setup, 'pio_path', return_value='/fake/pio'), patch.object(setup.subprocess, 'run') as run:
            run.return_value.returncode = 0
            setup.build('smartdb_s3', '/dev/ttyUSB0')
            self.assertEqual(run.call_args.args[0], ['/fake/pio','run','-e','smartdb_s3','-t','upload','--upload-port','/dev/ttyUSB0'])
            self.assertNotIn('shell', run.call_args.kwargs)

    def test_menu_exit_does_not_write_profile(self):
        with patch.object(setup, 'load_profile', return_value=profile()), patch('builtins.input', return_value='0'), patch.object(setup, 'save_profile') as save:
            setup.main(); save.assert_not_called()

    def test_camera_provisioning_without_reflash(self):
        data = profile(); data['settings'].update(telemetry_url='https://server.example/telemetry', telemetry_token='cloud-secret')
        calls = []
        class Camera:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def request(self, operation, payload=None, **kwargs):
                calls.append((operation, payload))
                return {'ok': True, 'protocol': 1, 'board': 'esp32cam', 'device_id': 'test-camera', 'ip': '192.168.1.72'}
        output = io.StringIO()
        with patch.object(setup, 'Device', return_value=Camera()), patch.object(setup, 'choose_port', return_value='fake'), patch.object(setup, 'save_profile') as save, patch.object(setup, 'build') as build, patch.object(setup.time, 'sleep'), redirect_stdout(output):
            setup.provision(data, 'esp32cam')
        build.assert_not_called(); save.assert_called_once()
        self.assertEqual(data['settings']['camera_url'], 'http://192.168.1.72/capture')
        sent = next(payload for operation, payload in calls if operation == 'save_settings')
        self.assertEqual(sent['telemetry_token'], '')
        self.assertEqual(sent['api_token'], data['settings']['api_token'])
        self.assertNotIn(data['settings']['wifi_password'], output.getvalue())
        self.assertNotIn(data['settings']['api_token'], output.getvalue())
        self.assertIn(('restart', None), calls)

    def test_wrong_board_never_saved_or_flashed(self):
        class Camera:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def request(self, operation, **kwargs):
                self.operation = operation
                return {'ok': True, 'protocol': 1, 'board': 'esp32cam'}
        camera = Camera()
        with patch.object(setup, 'Device', return_value=camera), patch.object(setup, 'choose_port', return_value='fake'), patch.object(setup, 'save_profile') as save, patch.object(setup, 'build') as build:
            with self.assertRaises(ValueError):
                setup.provision(profile(), 'smartdb_s3')
        self.assertEqual(camera.operation, 'info')
        save.assert_not_called(); build.assert_not_called()


if __name__ == '__main__':
    unittest.main()
