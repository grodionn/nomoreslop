#!/usr/bin/env python3
"""Check the declared brief and freshness of local design evidence, not its truth or taste.

init and snapshot write only a new explicitly named JSON file; check is read-only.
No network, browser, project execution, implicit source scan or package installation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SCHEMA_VERSION = 1
BRIEF_STATES = {'given', 'delegated', 'open', 'proposed', 'not_applicable'}
CHECK_STATES = {'required', 'passed', 'failed', 'unverified', 'not_applicable'}
KINDS = {'build', 'copy', 'function', 'visual', 'source_property', 'property'}


def local_path(root: Path, value: str) -> Path:
    if not isinstance(value, str) or not value.strip() or '\\' in value or re.match(r'^[A-Za-z]:', value):
        raise ValueError('Use a non-empty project-relative POSIX path.')
    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Path must stay inside the project.')
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError('Resolved path escapes the project.')
    return resolved


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nonempty(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def check_state(state, root: Path, stage: str = 'detail') -> dict:
    issues, pending, warnings = [], [], []
    if not isinstance(state, dict) or state.get('schema_version') != SCHEMA_VERSION:
        return {'status': 'invalid', 'issues': ['Expected schema_version:1 object.'], 'pending': [], 'warnings': [], 'limits': 'Structural checks do not authenticate decisions or observations.'}
    mode = state.get('mode', 'new')
    if mode not in {'new', 'redesign', 'local'}:
        issues.append('Unknown mode; use new, redesign or local.')
    brief = state.get('brief', [])
    if not isinstance(brief, list):
        issues.append('brief must be an array.'); brief = []
    ids = set()
    for item in brief:
        if not isinstance(item, dict):
            issues.append('Each brief item must be an object.'); continue
        identity = item.get('id')
        if not nonempty(identity) or identity in ids:
            issues.append('Brief IDs must be unique non-empty strings.'); continue
        ids.add(identity)
        status = item.get('status')
        if status not in BRIEF_STATES:
            issues.append(f'{identity}: unknown brief status.'); continue
        if not isinstance(item.get('required', True), bool):
            issues.append(f'{identity}: required must be boolean.')
        if status in {'given', 'delegated', 'not_applicable'}:
            basis = item.get('basis')
            if not isinstance(basis, dict) or basis.get('type') not in {'prompt', 'answer', 'delegation', 'project'} or not nonempty(basis.get('reference')) or not nonempty(basis.get('text')):
                issues.append(f'{identity}: closed decision needs actual basis type/reference/text.')
        elif item.get('required', True):
            pending.append(f'{identity}: {status}; dependent choice is unresolved.')
    if mode in {'new', 'redesign'}:
        if not brief:
            pending.append('No brief decisions recorded; contact alone does not establish sufficiency.')
        intent = state.get('intent', {})
        if not isinstance(intent, dict):
            issues.append('intent must be an object.'); intent = {}
        for key in ('visitor', 'material'):
            if not nonempty(intent.get(key)):
                pending.append(f'intent.{key} is missing.')
        if stage in {'composition', 'detail'} and not nonempty(intent.get('distinctive_result')):
            pending.append('intent.distinctive_result must describe the actual selected result, including a deliberate calm design.')
        content = state.get('content_path')
        if not nonempty(content):
            pending.append('content_path must reference the current exact content.')
        else:
            try:
                if not local_path(root, content).is_file():
                    issues.append('content_path does not exist.')
            except ValueError as error:
                issues.append('content_path: ' + str(error))

    checks = []
    top = state.get('checks', [])
    if isinstance(top, list):
        checks.extend(('project', check) for check in top)
    else:
        issues.append('checks must be an array.')
    decisions = state.get('decisions', [])
    if not isinstance(decisions, list):
        issues.append('decisions must be an array.'); decisions = []
    for decision in decisions:
        if not isinstance(decision, dict):
            issues.append('Each resource decision must be an object.'); continue
        nested = decision.get('checks', [])
        if not isinstance(nested, list):
            issues.append(str(decision.get('id', '?')) + ': checks must be an array.')
        else:
            checks.extend((str(decision.get('id', '?')), check) for check in nested)
    stale = []
    reported_passes = 0
    check_ids = set()
    for index, (scope, check) in enumerate(checks):
        if not isinstance(check, dict):
            issues.append(f'{scope}: check must be an object.'); continue
        identity = str(check.get('id') or f'{scope}/{index}')
        if identity in check_ids:
            issues.append(f'{identity}: duplicate check ID.')
        check_ids.add(identity)
        kind, status = check.get('kind'), check.get('status')
        if kind not in KINDS:
            issues.append(f'{identity}: unknown check kind.')
        if status not in CHECK_STATES:
            issues.append(f'{identity}: unknown check status.'); continue
        if status in {'unverified', 'not_applicable'} and not nonempty(check.get('reason')):
            issues.append(f'{identity}: {status} requires a concrete reason.')
        if status == 'failed':
            issues.append(f'{identity}: reported failure remains unresolved.')
        if status in {'required', 'unverified'} and check.get('required', True):
            pending.append(f'{identity}: {status}.')
        if status != 'passed':
            continue
        reported_passes += 1
        for key in ('action', 'observation'):
            if not nonempty(check.get(key)):
                issues.append(f'{identity}: passed check needs {key}.')
        evidence = check.get('evidence')
        if not isinstance(evidence, list) or not evidence or not all(nonempty(e) for e in evidence):
            issues.append(f'{identity}: passed check needs non-empty evidence references.')
        environment = check.get('environment')
        if not isinstance(environment, dict) or not environment:
            issues.append(f'{identity}: passed check needs actual environment metadata.')
        files = check.get('files')
        if not isinstance(files, dict) or not files:
            issues.append(f'{identity}: passed check needs hashes of the relevant current files.'); continue
        for relative, digest in files.items():
            try:
                target = local_path(root, relative)
                if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
                    issues.append(f'{identity}: invalid SHA256 for {relative}.'); continue
                if not target.is_file() or file_hash(target) != digest:
                    stale.append({'check': identity, 'path': relative})
            except (OSError, ValueError) as error:
                issues.append(f'{identity}: {relative}: {error}')
        if kind == 'visual':
            method = str(environment.get('method', '')).lower()
            if method not in {'browser-render', 'native-render', 'device-render'}:
                issues.append(f'{identity}: visual evidence needs an actual render method, not a DOM harness.')
            if not environment.get('viewport') and not nonempty(environment.get('device')):
                issues.append(f'{identity}: visual evidence needs viewport or device.')
    if stale:
        pending.extend(f'{row["check"]}: stale evidence after change to {row["path"]}.' for row in stale)
    if stage == 'detail' and not checks:
        pending.append('No checks recorded for the current result.')
    warnings.append('Decision basis, action, observations, environment and evidence are agent/user declarations; hashes only verify byte freshness.')
    warnings.append('Use resource_pipeline.py coverage for candidate/package/application checks; this command does not evaluate craft or source influence.')
    return {'status': 'invalid' if issues else 'incomplete' if pending else 'structurally_consistent',
            'stage': stage, 'mode': mode, 'issues': issues, 'pending': pending, 'warnings': warnings,
            'stale': stale, 'reported_passes': reported_passes,
            'limits': 'No truth authentication, aesthetic grade, runtime execution, network or automatic approval.'}


def write_new(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='Create an unresolved state template; does not approve any decision.')
    init.add_argument('--output', type=Path, required=True)
    init.add_argument('--mode', choices=('new', 'redesign', 'local'), default='new')
    check = commands.add_parser('check', help='Read declared decisions and verify current relevant hashes.')
    check.add_argument('state', type=Path)
    check.add_argument('--project', type=Path, required=True)
    check.add_argument('--stage', choices=('content', 'composition', 'detail', 'local'), default='detail')
    snapshot = commands.add_parser('snapshot', help='Hash only explicitly selected local project files.')
    snapshot.add_argument('--project', type=Path, required=True)
    snapshot.add_argument('--path', action='append', required=True)
    snapshot.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'init':
            template = {'schema_version': 1, 'mode': args.mode, 'content_path': '',
                        'intent': {'visitor': '', 'material': '', 'distinctive_result': ''},
                        'brief': [] if args.mode == 'local' else [
                            {'id': key, 'topic': topic, 'required': True, 'status': 'open',
                             'basis': {'type': '', 'reference': '', 'text': ''}}
                            for key, topic in [('purpose', 'Visitor and intended outcome'), ('material', 'Available verified material'), ('direction', 'Significant design decisions and requested behavior')]],
                        'research_profile': {'origin': '', 'basis': '', 'tags': {'style': [], 'composition': [], 'ux': [], 'platform': []}},
                        'decisions': [], 'checks': [], 'next': 'Record actual known decisions and ask only substantial unresolved questions.'}
            write_new(args.output, template)
            result = {'created': str(args.output), 'status': 'unresolved_template'}
        else:
            root = args.project.resolve()
            if not root.is_dir():
                raise ValueError('Project must be an existing directory.')
            if args.command == 'check':
                state = json.loads(args.state.read_text(encoding='utf-8-sig'))
                result = check_state(state, root, args.stage)
            else:
                result = {'files': {value: file_hash(local_path(root, value)) for value in dict.fromkeys(args.path)}}
                if args.output:
                    for value in args.path:
                        if args.output.resolve() == local_path(root, value):
                            raise ValueError('Snapshot cannot overwrite an input file.')
                    write_new(args.output, result)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0 if args.command != 'check' or result['status'] == 'structurally_consistent' else 1
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError) as error:
        parser.exit(2, f'design_state: {error}\n')


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
