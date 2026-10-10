"""Exercise checked-in firmware request bodies against the Postman contracts."""
import copy
import json
import re
from pathlib import Path
import unittest
import yaml
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[3] / 'postman'
API = yaml.safe_load((ROOT / 'specs/smartdb_api/openapi.yaml').read_text())
LOCAL = yaml.safe_load((ROOT / 'specs/smartdb_firmware/openapi.yaml').read_text())
REGISTRY = Registry().with_resource('urn:smartdb:api', Resource.from_contents({
    '$schema': 'https://json-schema.org/draft/2020-12/schema', **API}))

def telemetry_validator():
    return Draft202012Validator({'$ref': 'urn:smartdb:api#/components/schemas/Telemetry'},
                                registry=REGISTRY, format_checker=FormatChecker())

def upload():
    request = yaml.safe_load((ROOT / 'collections/smartdb_api/telemetry/upload_telemetry.request.yaml').read_text())
    return json.loads(request['body']['content'])

class PostmanContract(unittest.TestCase):
    def test_bench_upload(self):
        data = upload()
        telemetry_validator().validate(data)
        self.assertIsNone(data['voltage'])
        self.assertIsNone(data['power'])
        self.assertFalse(data['arc_detection_available'])

    def test_unknown_and_stale(self):
        data = upload()
        data.update(timestamp=None, current=None, temperature=None, time_quality='unknown')
        telemetry_validator().validate(data)

    def test_legacy_measurements_remain_supported(self):
        telemetry_validator().validate(dict(voltage=12, current=.3, power=3.6,
                                            temperature=30, timestamp='2026-10-10T00:00:00Z'))

    def test_bad_current_and_vision_rejected(self):
        for field, value in [('current', -.1), ('timestamp', 123)]:
            data = upload(); data[field] = value
            self.assertTrue(list(telemetry_validator().iter_errors(data)))
        data = upload(); data['vision']['regions'][0]['samples'] = 769
        self.assertTrue(list(telemetry_validator().iter_errors(data)))

    def test_config_limits(self):
        validator = Draft202012Validator(LOCAL['components']['schemas']['Config'])
        request = yaml.safe_load((ROOT / 'collections/smartdb_api/firmware/set_config.request.yaml').read_text())
        data = json.loads(request['body']['content']); validator.validate(data)
        for field, value in [('current_limit_a', 1.1), ('version', 1.5), ('commissioned', 'true'), ('temperature_limit_c', 101)]:
            invalid = copy.deepcopy(data); invalid[field] = value
            self.assertTrue(list(validator.iter_errors(invalid)))

    def test_yaml_and_linked_examples(self):
        for path in ROOT.rglob('*.yaml'):
            doc = yaml.safe_load(path.read_text())
            if 'firmware' in path.parts and path.name.endswith('.request.yaml'):
                examples = list((path.parent / doc['examples']).glob('*.yaml'))
                self.assertTrue(examples)
                for example in examples:
                    saved = yaml.safe_load(example.read_text())['request']
                    self.assertEqual(saved['url'], doc['url'])
                    self.assertEqual(saved['method'], doc['method'])
                    self.assertEqual(saved.get('body'), doc.get('body'))

    def test_device_response_and_unseen_status(self):
        Draft202012Validator(API['components']['schemas']['Device']).validate({
            'device_id': 'bench-1', 'device_name': 'Bench', 'device_type': 'ESP32',
            'location': 'Lab', 'status': 'registered'})
        Draft202012Validator(API['components']['schemas']['DeviceStatus']).validate({
            'online': False, 'last_seen': None, 'firmware': '', 'config_version': None})

    def test_cloud_limits_and_no_remote_close(self):
        config = Draft202012Validator(API['components']['schemas']['DeviceConfig'])
        config.validate(dict(max_temperature=60, max_current=.8, sampling_rate=5))
        self.assertTrue(list(config.iter_errors(dict(max_temperature=60, max_current=2, sampling_rate=5))))
        command = Draft202012Validator(API['components']['schemas']['Command'])
        command.validate({'command': 'SET_INTERVAL', 'value': 10})
        self.assertTrue(list(command.iter_errors({'command': 'SET_INTERVAL', 'value': 1})))
        self.assertTrue(list(command.iter_errors({'command': 'CLOSE_RELAY'})))

    def test_all_central_json_requests_and_saved_responses(self):
        for path in (ROOT / 'collections/smartdb_api').rglob('*.yaml'):
            doc = yaml.safe_load(path.read_text())
            request = doc.get('request', doc)
            url = request.get('url', '')
            if not isinstance(url, str) or not url.startswith('{{base_url}}'):
                continue
            route = re.sub(r'\{\{([^}]+)\}\}', r'{\1}', url.removeprefix('{{base_url}}').split('?')[0])
            operation = API['paths'][route][request['method'].lower()]
            pairs = [(request.get('body'), operation.get('requestBody', {}).get('content', {}).get('application/json', {}).get('schema'))]
            if 'response' in doc:
                response = doc['response']
                definition = operation['responses'].get(str(response['statusCode']), {})
                pairs.append((response.get('body'), definition.get('content', {}).get('application/json', {}).get('schema')))
            for body, schema in pairs:
                if body and schema and body.get('type') == 'json':
                    with self.subTest(path=str(path)):
                        Draft202012Validator({'components': API['components'], **schema}).validate(json.loads(body['content']))

if __name__ == '__main__':
    unittest.main()
