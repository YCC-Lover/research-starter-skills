"""Retain native screening returns and replay all returns when merging a stage."""

import argparse
import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from research_engine import local_environment, run_local


def collect(plan_path, label, response_path, actor_context_id):
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    if plan.get('schema') != 'rsk.screening-dispatch.v1':
        raise ValueError('Expected a native screening dispatch plan.')
    matches = [row for row in plan['calls'] if row['label'] == label]
    if len(matches) != 1 or not isinstance(actor_context_id, str) or not actor_context_id.strip():
        raise ValueError('One planned call and its observed actor context ID are required.')
    call = matches[0]
    if not label.endswith('@' + plan['context']['context_id']):
        raise ValueError('Call does not match the plan context.')
    prompt_hash = hashlib.sha256(Path(call['prompt_file']).read_bytes()).hexdigest()
    if prompt_hash != call['prompt_sha256']:
        raise ValueError('Prompt bytes changed after dispatch.')
    raw = Path(response_path).read_bytes()
    response = json.loads(raw)
    if not isinstance(response, dict) or not isinstance(response.get('decisions'), list):
        raise ValueError('Expected the actual worker JSON object with a decisions array.')
    work, _ = local_environment(plan['work'])
    folder = work / 'codex-results'
    if folder.is_symlink() or (folder.exists() and not folder.is_dir()):
        raise ValueError('Invalid result directory.')
    # Validate this directory and all ancestors before writing retained returns.
    local_environment(folder)
    for previous in folder.glob('*.meta.json'):
        metadata = json.loads(previous.read_text(encoding='utf-8'))
        if (metadata.get('context_id') == plan['context']['context_id'] and
                metadata.get('actor_context_id') == actor_context_id and
                metadata.get('role') != call['role']):
            raise ValueError('Different screening roles must use different actor contexts.')
    token = uuid.uuid4().hex
    result_path = folder / (token + '.json')
    receipt_path = folder / (token + '.meta.json')
    result = {'label': label, 'context': plan['context'], 'decisions': response['decisions']}
    receipt = {'schema': 'rsk.screening-return.v1', 'label': label, 'role': call['role'],
               'context_id': plan['context']['context_id'], 'actor_context_id': actor_context_id,
               'prompt_sha256': prompt_hash, 'raw_response_sha256': hashlib.sha256(raw).hexdigest(),
               'raw_response': str(Path(response_path).absolute()),
               'result_sha256': hashlib.sha256((json.dumps(result, ensure_ascii=True, indent=2) + '\n').encode()).hexdigest(),
               'received_at': datetime.now(timezone.utc).isoformat(),
               'identity_source': 'caller_recorded_not_independently_attested',
               'model_identity': 'unknown'}
    with receipt_path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(receipt, ensure_ascii=True, indent=2) + '\n')
    with result_path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(result, ensure_ascii=True, indent=2) + '\n')
    return {'result': str(result_path), 'receipt': str(receipt_path),
            'merge_source': str(folder), 'worker_executed_by_this_script': False}


def merge(work_dir, stage, config=None):
    work, _ = local_environment(work_dir)
    folder = work / 'codex-results'
    if not folder.is_dir():
        raise ValueError('Collect actual native returns before merging.')
    local_environment(folder)
    results = list(folder.glob('*.json'))
    results = [path for path in results if not path.name.endswith('.meta.json')]
    if not results:
        raise ValueError('No retained native screening returns.')
    for result in results:
        receipt = json.loads(result.with_name(result.stem + '.meta.json').read_text(encoding='utf-8'))
        if hashlib.sha256(result.read_bytes()).hexdigest() != receipt['result_sha256']:
            raise ValueError('Retained result bytes differ from their receipt.')
    arguments = ['--work', str(work), '--stage', stage, '--from', str(folder)]
    if config is not None:
        arguments.extend(['--config', str(Path(config).absolute())])
    return run_local('sr-screener/scripts/merge_decisions.py', arguments, work)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    add = commands.add_parser('collect')
    for option in ('plan', 'label', 'response', 'actor-context-id'):
        add.add_argument('--' + option, required=True)
    combine = commands.add_parser('merge')
    combine.add_argument('--work-dir', required=True, type=Path)
    combine.add_argument('--stage', choices=('ta', 'ft'), required=True)
    combine.add_argument('--config', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'merge':
            return merge(args.work_dir, args.stage, args.config)
        print(json.dumps(collect(args.plan, args.label, args.response, args.actor_context_id), indent=2))
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'Native screening return refused: ' + str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
