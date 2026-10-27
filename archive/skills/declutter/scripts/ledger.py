#!/usr/bin/env python3
"""Verify previously removed programs and record Keep/Remove decisions.

Usage: ledger.py [-h | --help] [--log PATH] check
       ledger.py [--log PATH] decide ID --choice keep|remove
       ledger.py help

The YAML log defaults to ~/dot_local/app_cleanup.yaml. Check is read-only:
it matches installed app paths, names and bundle IDs in /Applications and
~/Applications, plus Homebrew cask/formula registrations. It reports reinstalled
programs even when the declutter ignore list hides them. Keep records an allowed
installation; Remove records intent only, never deletes anything. delete.py
records verified removals automatically. PyYAML is required.

Exit 0 for a completed check or decision; exit 1 if the log or inventory cannot
be read or written. Inventory failures must not be interpreted as absence.
"""
import argparse
import json
import os
import plistlib
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import yaml

LOG = Path.home() / 'dot_local' / 'app_cleanup.yaml'
APP_DIRS = [Path('/Applications'), Path.home() / 'Applications']


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def load(path=LOG):
    if not Path(path).exists():
        return {'schema_version': 1, 'program': []}
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict) or not isinstance(data.get('program', []), list):
        raise ValueError(f'invalid program log: {path}')
    data.setdefault('program', [])
    for item in data['program']:
        if (not isinstance(item, dict) or item.get('kind') not in {'app', 'formula', 'cask'}
                or not item.get('id') or not item.get('name') or not item.get('path')
                or item.get('expected') not in {'absent', 'allowed'}):
            raise ValueError(f'invalid program record: {item}')
    return data


def save(data, path=LOG):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Replace atomically so an interrupted write cannot truncate removal history.
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent,
                                     prefix='.app_cleanup_', delete=False) as file:
        yaml.safe_dump(data, file, sort_keys=False, allow_unicode=True)
        temp = file.name
    os.replace(temp, path)


def app_paths(roots=APP_DIRS):
    def fail(error):
        raise error
    for root in roots:
        if not root.exists():
            continue
        for base, dirs, _ in os.walk(root, onerror=fail):
            for name in list(dirs):
                if name.endswith('.app'):
                    dirs.remove(name)
                    yield Path(base) / name


def bundle(path):
    info = Path(path) / 'Contents' / 'Info.plist'
    if not info.exists():
        return ''
    with info.open('rb') as file:
        return plistlib.load(file).get('CFBundleIdentifier', '')


def identity(item):
    kind = item['kind']
    token = item.get('token') or item.get('cask') or item['name']
    name = item['name']
    path = item['path']
    bid = item.get('bundle_id', '')
    if Path(path).suffix == '.app' and not bid:
        bid = bundle(path)
    key = token if kind in {'formula', 'cask'} else bid or name.casefold()
    result = {'id': f'{kind}:{key}', 'kind': kind, 'name': name, 'path': path}
    if kind in {'formula', 'cask'}:
        result['token'] = token
    if bid:
        result['bundle_id'] = bid
    return result


def inventory(program):
    result = {'app': [], 'formula': set(), 'cask': set(), 'error': {}}
    if any(p['kind'] in {'app', 'cask'} for p in program):
        try:
            result['app'] = [{'path': str(path), 'name': path.stem,
                              'bundle_id': bundle(path)} for path in app_paths()]
        except (OSError, plistlib.InvalidFileException) as error:
            result['error']['app'] = str(error)
    for kind in {'formula', 'cask'} & {p['kind'] for p in program}:
        flag = '--formula' if kind == 'formula' else '--cask'
        try:
            output = subprocess.run(['brew', 'list', flag], capture_output=True,
                                    text=True, check=True, timeout=30)
            result[kind] = set(output.stdout.splitlines())
        except (OSError, subprocess.SubprocessError) as error:
            result['error'][kind] = str(error)
    return result


def presence(item, installed):
    kind = item['kind']
    if os.path.lexists(item['path']):
        return 'installed', [item['path']]
    if kind in {'formula', 'cask'} and item.get('token', item['name']) in installed[kind]:
        return 'installed', [f"Homebrew {kind}: {item.get('token', item['name'])}"]
    if kind in {'app', 'cask'}:
        bid = item.get('bundle_id')
        name = Path(item['path']).stem if Path(item['path']).suffix == '.app' else item['name']
        matches = [app['path'] for app in installed['app']
                   if bid and app['bundle_id'] == bid or app['name'].casefold() == name.casefold()]
        if matches:
            return 'installed', matches
    error = [installed['error'][key] for key in ({kind, 'app'} if kind == 'cask' else {kind})
             if key in installed['error']]
    if error:
        return 'unknown', error
    return 'absent', []


def check(path=LOG):
    data = load(path)
    installed = inventory(data['program'])
    result = {'log': str(path), 'checked_at': now(), 'verified_absent': [],
              'reinstalled': [], 'allowed': [], 'unknown': []}
    for item in data['program']:
        state, evidence = presence(item, installed)
        row = {'id': item['id'], 'name': item['name'], 'kind': item['kind'],
               'status': state, 'evidence': evidence}
        if state == 'unknown':
            result['unknown'].append(row)
            continue
        if item['expected'] == 'allowed':
            result['allowed'].append(row)
            continue
        if state == 'installed':
            result['reinstalled'].append(row)
            continue
        result['verified_absent'].append(row)
    return result


def record(item, method, path=LOG):
    item = identity(item)
    state, evidence = presence(item, inventory([item]))
    if state != 'absent':
        raise ValueError(f"removal not verified for {item['name']}: {state} {evidence}")
    data = load(path)
    previous = next((p for p in data['program'] if p['id'] == item['id']), None)
    if previous is None:
        previous = item
        data['program'].append(previous)
    previous.update(item)
    previous['expected'] = 'absent'
    previous.setdefault('removal', []).append({'removed_at': now(), 'method': method,
                                             'verified_at': now(), 'result': 'absent'})
    save(data, path)


def decide(key, choice, path=LOG):
    if choice not in {'keep', 'remove'}:
        raise ValueError('choice must be keep or remove')
    data = load(path)
    item = next((p for p in data['program'] if p['id'] == key), None)
    if item is None:
        raise ValueError(f'program not in removal log: {key}')
    item['expected'] = 'allowed' if choice == 'keep' else 'absent'
    item.setdefault('decision', []).append({'at': now(), 'choice': choice})
    save(data, path)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if 'help' in argv:
        print(__doc__)
        return 0
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--log', type=Path, default=LOG, help='YAML program log')
    command = parser.add_subparsers(dest='command', required=True)
    command.add_parser('check', help='verify every recorded program; read-only')
    decision = command.add_parser('decide', help='record an explicit user decision')
    decision.add_argument('id')
    decision.add_argument('--choice', choices=['keep', 'remove'], required=True)
    args = parser.parse_args(argv)
    if args.command == 'decide':
        decide(args.id, args.choice, args.log)
        print(f'{args.id}: {args.choice} recorded; no program removed')
        return 0
    result = check(args.log)
    print(json.dumps(result, indent=2))
    return 1 if result['unknown'] else 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(1)
