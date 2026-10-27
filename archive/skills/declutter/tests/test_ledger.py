#!/usr/bin/env python3
"""Verify removal logging and reinstall decisions using disposable inventories."""
import json
import plistlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import ledger
import delete as remove


class Ledger(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / 'app_cleanup.yaml'
        self.item = {'kind': 'app', 'name': 'Example',
                     'path': str(self.root / 'Example.app'), 'bundle_id': 'org.test.example'}
        self.empty = {'app': [], 'formula': set(), 'cask': set(), 'error': {}}

    def record(self):
        with patch.object(ledger, 'inventory', return_value=self.empty):
            ledger.record(self.item, 'move_to_trash', self.log)

    def test_successful_removal_preserves_existing_log(self):
        ledger.save({'schema_version': 1, 'event': [{'status': 'reviewed'}],
                     'program': []}, self.log)
        self.record()
        data = ledger.load(self.log)
        self.assertEqual(data['event'], [{'status': 'reviewed'}])
        self.assertEqual(data['program'][0]['expected'], 'absent')
        self.assertEqual(data['program'][0]['removal'][0]['result'], 'absent')
        with patch.object(ledger, 'inventory', return_value=self.empty):
            self.assertEqual(len(ledger.check(self.log)['verified_absent']), 1)

    def test_reinstalled_app_with_new_name_and_path(self):
        self.record()
        installed = {**self.empty, 'app': [{'path': '/Applications/Renamed.app',
                       'name': 'Renamed', 'bundle_id': 'org.test.example'}]}
        with patch.object(ledger, 'inventory', return_value=installed):
            result = ledger.check(self.log)
        self.assertEqual(result['reinstalled'][0]['name'], 'Example')
        self.assertEqual(result['reinstalled'][0]['evidence'], ['/Applications/Renamed.app'])

    def test_keep_then_remove_preserves_history(self):
        self.record()
        key = ledger.load(self.log)['program'][0]['id']
        installed = {**self.empty, 'app': [{'path': '/Applications/Example.app',
                       'name': 'Example', 'bundle_id': 'org.test.example'}]}
        ledger.decide(key, 'keep', self.log)
        with patch.object(ledger, 'inventory', return_value=installed):
            result = ledger.check(self.log)
            self.assertEqual(result['reinstalled'], [])
            self.assertEqual(len(result['allowed']), 1)
            ledger.decide(key, 'remove', self.log)
            self.assertEqual(len(ledger.check(self.log)['reinstalled']), 1)
        self.assertEqual(len(ledger.load(self.log)['program'][0]['removal']), 1)
        self.assertEqual(len(ledger.load(self.log)['program'][0]['decision']), 2)

    def test_still_installed_never_recorded(self):
        Path(self.item['path']).mkdir()
        with patch.object(ledger, 'inventory', return_value=self.empty):
            with self.assertRaisesRegex(ValueError, 'removal not verified'):
                ledger.record(self.item, 'move_to_trash', self.log)
        self.assertFalse(self.log.exists())

    def test_inventory_failure_never_means_absent(self):
        broken = {**self.empty, 'error': {'app': 'permission denied'}}
        with patch.object(ledger, 'inventory', return_value=broken):
            with self.assertRaisesRegex(ValueError, 'unknown'):
                ledger.record(self.item, 'move_to_trash', self.log)
        self.record()
        with patch.object(ledger, 'inventory', return_value=broken):
            self.assertEqual(len(ledger.check(self.log)['unknown']), 1)

    def test_cask_token_survives_identity_roundtrip(self):
        item = {**self.item, 'kind': 'cask', 'name': 'Friendly Name', 'cask': 'example-cask'}
        captured = ledger.identity(item)
        self.assertEqual(ledger.identity(captured)['token'], 'example-cask')
        with patch.object(ledger, 'inventory', return_value=self.empty):
            ledger.record(captured, 'brew_uninstall_permanent', self.log)
        installed = {**self.empty, 'cask': {'example-cask'}}
        with patch.object(ledger, 'inventory', return_value=installed):
            self.assertEqual(len(ledger.check(self.log)['reinstalled']), 1)

    def test_homebrew_failure_reported_as_unknown(self):
        formula = {'kind': 'formula', 'name': 'example', 'path': str(self.root / 'missing')}
        with patch.object(ledger.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'brew')):
            installed = ledger.inventory([formula])
        self.assertEqual(ledger.presence(formula, installed)[0], 'unknown')

    def test_nested_apps_without_bundle_helpers(self):
        app = self.root / 'nested' / 'Example.app'
        helper = app / 'Contents' / 'Helper.app'
        helper.mkdir(parents=True)
        self.assertEqual(list(ledger.app_paths([self.root])), [app])

    def test_dry_run_does_not_create_log(self):
        item = {**self.item, 'path': '/Applications/Example.app'}
        self.assertIn('would trash', remove.plan(item, False, self.log))
        self.assertFalse(self.log.exists())

    def test_execute_logs_real_trash_and_keeps_bundle_id(self):
        app = Path(self.item['path'])
        info = app / 'Contents' / 'Info.plist'
        info.parent.mkdir(parents=True)
        info.write_bytes(plistlib.dumps({'CFBundleIdentifier': 'org.test.example'}))
        trash = self.root / 'trash'
        trash.mkdir()
        item = {k: v for k, v in self.item.items() if k != 'bundle_id'}
        with patch.object(remove, 'TRASH', trash), patch.object(remove, 'safe', return_value=True), \
                patch.object(remove, 'running', return_value=False), \
                patch.object(ledger, 'inventory', return_value=self.empty):
            self.assertTrue(remove.plan(item, True, self.log).startswith('trashed'))
        self.assertFalse(app.exists())
        self.assertTrue((trash / 'Example.app').exists())
        self.assertEqual(ledger.load(self.log)['program'][0]['bundle_id'], 'org.test.example')

    def test_failed_homebrew_uninstall_not_logged(self):
        item = {'kind': 'cask', 'name': 'Example', 'path': str(self.root / 'missing'), 'cask': 'example'}
        with patch.object(remove, 'safe', return_value=True), \
                patch.object(remove, 'running', return_value=False), \
                patch.object(remove, 'run', side_effect=RuntimeError('uninstall failed')):
            with self.assertRaisesRegex(RuntimeError, 'uninstall failed'):
                remove.plan(item, True, self.log)
        self.assertFalse(self.log.exists())

    def test_running_app_is_blocked_before_mutation(self):
        item = {**self.item, 'path': '/Applications/Example.app'}
        with patch.object(remove, 'running', return_value=True), patch.object(remove, 'trash') as trash:
            self.assertTrue(remove.plan(item, True, self.log).startswith('BLOCKED'))
            trash.assert_not_called()
        self.assertFalse(self.log.exists())

    def test_scan_checks_history_even_when_ignored(self):
        import contextlib
        import io
        import scan
        result = {'verified_absent': [], 'unknown': [], 'reinstalled': [{'id': 'app:example'}]}
        output = io.StringIO()
        with patch.object(ledger, 'check', return_value=result), \
                patch.object(scan, 'scan_apps', return_value=([], {})), \
                patch.object(scan, 'scan_formulae', return_value=[]), \
                patch.object(scan, 'scan_leftovers', return_value=[]), \
                patch.object(scan, 'scan_files', return_value=[]), \
                patch.object(scan, 'load_ignored', return_value={self.item['path']}), \
                contextlib.redirect_stdout(output):
            scan.main()
        self.assertEqual(json.loads(output.getvalue())['reinstall_check']['reinstalled'], result['reinstalled'])


if __name__ == '__main__':
    unittest.main()
