import copy
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('log_rotation', ROOT / 'scripts/apply-log-rotation.py')
rotation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rotation)
POLICY = {'Type': 'json-file', 'Config': {'max-size': '100000000', 'max-file': '10'}}
COMPOSE = ['docker', 'compose', '-p', 'olympus', '-f', 'compose.prod.yaml',
           '-f', 'compose.logging.yaml', '-f', 'compose.prod.cleanup.yaml']


def container(service, status='running', policy=None):
    return {'Id': service + '-id', 'Image': 'sha256:' + service,
            'State': {'Status': status, 'Health': {'Status': 'healthy'}},
            'HostConfig': {'LogConfig': policy or {'Type': 'json-file', 'Config': {}}},
            'Config': {'Labels': {'com.docker.compose.service': service,
                                 'com.docker.compose.config-hash': service + '-hash'}, 'Image': service + ':latest'}}


class LogRotationTest(unittest.TestCase):
    def setUp(self):
        self.containers = [container('database'), container('web'), container('setup', 'exited')]
        self.model = {'services': {c['Config']['Labels']['com.docker.compose.service']: {
            'logging': {'driver': POLICY['Type'], 'options': POLICY['Config']}}
            for c in self.containers}}
        self.model['services']['web']['depends_on'] = {'database': {}}
        self.runs = []
        self.completed = []
        self.image_resolver = lambda reference: reference
        self.expected_images = {}

    def output(self, command):
        if command[-3:] == ['config', '--format', 'json']:
            return json.dumps(self.model)
        if command[-3:] == ['config', '--hash', '*']:
            self.assertNotIn('compose.logging.yaml', command)
            self.assertIn('compose.prod.cleanup.yaml', command)
            return '\n'.join(s + ' ' + s + '-hash' for s in self.model['services'])
        if command[-3:] == ['ps', '--all', '--quiet']:
            return '\n'.join(c['Id'] for c in self.containers)
        raise AssertionError(command)

    def inspect(self, ids):
        return [copy.deepcopy(c) for c in self.containers if c['Id'] in ids]

    def run_command(self, command, check):
        self.assertTrue(check)
        self.runs.append(command)
        if 'up' in command:
            image_file = Path(command[command.index('up') - 1])
            images = json.loads(image_file.read_text())['services']
            for service in images:
                self.assertEqual(self.expected_images.get(service, 'sha256:' + service), images[service]['image'])
                self.assertEqual('never', images[service]['pull_policy'])
            self.assertNotIn('setup', images)
        return subprocess.CompletedProcess(command, 0)

    def apply(self, allow_current_images=False):
        with patch.object(rotation, 'output', side_effect=self.output), \
                patch.object(rotation, 'inspect', side_effect=self.inspect), \
                patch.object(rotation, 'image_id', side_effect=self.image_resolver), \
                patch.object(rotation.subprocess, 'run', side_effect=self.run_command), \
                patch.object(rotation, 'ready', side_effect=lambda *args: self.completed.append(args)):
            rotation.apply(COMPOSE, allow_current_images)

    def test_only_running_services_recreated_with_same_images_and_no_dependencies(self):
        self.apply()
        ups = [c for c in self.runs if 'up' in c]
        self.assertEqual(['database', 'web'], [c[-1] for c in ups])
        for command in ups:
            self.assertEqual(['up', '-d', '--no-deps', '--no-build', '--pull', 'never',
                              '--force-recreate', command[-1]], command[command.index('up'):])
        self.assertEqual(2, len(self.completed))
        self.assertTrue(all(c[-1] for c in self.completed))  # previous health is checked

    def test_drift_in_later_service_aborts_before_any_recreation(self):
        self.containers[1]['Config']['Labels']['com.docker.compose.config-hash'] = 'unrelated-change'
        with self.assertRaisesRegex(RuntimeError, 'unrelated Compose configuration drift'):
            self.apply()
        self.assertEqual([], self.runs)

    def test_already_rotated_services_are_not_restarted_again(self):
        for item in self.containers:
            item['HostConfig']['LogConfig'] = copy.deepcopy(POLICY)
        self.apply()
        self.assertEqual([], self.runs)

    def test_unavailable_old_image_is_deferred_without_restarting_that_service(self):
        self.image_resolver = lambda reference: None if reference == 'sha256:web' else reference
        with self.assertRaisesRegex(RuntimeError, 'still deferred: web'):
            self.apply()
        self.assertEqual(['database'], [c[-1] for c in self.runs if 'up' in c])

    def test_explicit_image_change_uses_available_local_image_without_pulling(self):
        self.image_resolver = lambda reference: (None if reference == 'sha256:web'
                                                else 'sha256:web-new' if reference == 'web:latest'
                                                else reference)
        self.expected_images['web'] = 'sha256:web-new'
        self.apply(allow_current_images=True)
        self.assertEqual('sha256:web-new', self.completed[-1][2])
        ups = [c for c in self.runs if 'up' in c]
        self.assertTrue(all('--no-build' in c and c[c.index('--pull') + 1] == 'never' for c in ups))

    def test_ready_rejects_changed_image_or_missing_effective_policy(self):
        for change, error in [('Image', 'image changed'), ('HostConfig', 'log policy')]:
            with self.subTest(change=change):
                current = container('web', policy=copy.deepcopy(POLICY))
                current[change] = 'different-image' if change == 'Image' else {'LogConfig': {}}
                with patch.object(rotation, 'output', return_value='new-id'), \
                        patch.object(rotation, 'inspect', return_value=[current]):
                    with self.assertRaisesRegex(RuntimeError, error):
                        rotation.ready(COMPOSE, 'web', 'sha256:web', POLICY, True)

    def test_readiness_waits_for_previously_healthy_service(self):
        starting = container('web', policy=copy.deepcopy(POLICY))
        starting['State']['Health']['Status'] = 'starting'
        healthy = container('web', policy=copy.deepcopy(POLICY))
        with patch.object(rotation, 'output', return_value='new-id'), \
                patch.object(rotation, 'inspect', side_effect=[[starting], [healthy]]), \
                patch.object(rotation.time, 'sleep') as sleep:
            rotation.ready(COMPOSE, 'web', 'sha256:web', POLICY, True)
            sleep.assert_called_once_with(2)

    def test_cli_rejects_logging_only_combined_with_app_or_development(self):
        for args in [('dev', 'up', '--logging-only'),
                     ('prod', 'up', 'stagemanager', '--logging-only'),
                     ('prod', 'up', '--logging-only', '--prepare-only')]:
            result = subprocess.run([str(ROOT / 'olymctl'), *args], capture_output=True, text=True)
            self.assertNotEqual(0, result.returncode)
            self.assertIn('--logging-only requires prod up', result.stderr)

    def test_compose_policy_covers_all_production_services_with_one_gigabyte_budget(self):
        model = json.loads(subprocess.check_output([
            'docker', 'compose', '-p', 'logging-test', '-f', str(ROOT / 'compose.logging.yaml'),
            'config', '--format', 'json', '--no-consistency'], text=True))
        declared = {'reverse-proxy'}
        for source in ('compose.yaml', 'compose.prod.yaml'):
            services_section = (ROOT / source).read_text().split('\nservices:\n', 1)[1]
            services_section = re.split(r'\n[^ #\n]', services_section, maxsplit=1)[0]
            declared.update(re.findall(r'^  ([a-z][a-z0-9-]*):', services_section, re.M))
        self.assertEqual(declared, set(model['services']))
        for service in model['services'].values():
            options = service['logging']['options']
            self.assertEqual('json-file', service['logging']['driver'])
            self.assertEqual(1_000_000_000, int(options['max-size']) * int(options['max-file']))


if __name__ == '__main__':
    unittest.main()
