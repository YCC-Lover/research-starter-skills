"""Check recorded evaluation integrity, not model correctness or tool execution."""

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def source_text(root, relative):
    path = root / relative
    require(not Path(relative).is_absolute() and not path.is_symlink()
            and path.resolve().is_relative_to(root), 'Unsafe evaluation source path.')
    return path.read_text(encoding='utf-8')


def snapshot(root):
    root = Path(root).resolve()
    cases = json.loads(source_text(root, 'evals/cases.json'))
    inputs = {name: source_text(root, name) for case in cases['cases'] for name in case['files']}
    skills = {path.relative_to(root).as_posix(): source_text(root, path.relative_to(root).as_posix())
              for path in sorted((root / 'skills').rglob('*')) if path.is_file()}
    return {'cases_sha256': digest(cases), 'inputs_sha256': digest(inputs),
            'skills_sha256': digest(skills),
            'skill_files_sha256': {name: hashlib.sha256(text.encode('utf-8')).hexdigest()
                                   for name, text in skills.items()}}


def validate(root=ROOT):
    root = Path(root).resolve()
    cases = json.loads(source_text(root, 'evals/cases.json'))['cases']
    case_map = {case['id']: case for case in cases}
    require(len(case_map) == len(cases) and cases, 'Duplicate or empty evaluation cases.')
    report = json.loads(source_text(root, 'evals/results.json'))
    catalog = json.loads(source_text(root, 'catalog.json'))
    require(report['package_version'] == catalog['version'], 'Evaluation package version mismatch.')
    require(report['snapshot'] == snapshot(root), 'Evaluation inputs or skill snapshot changed.')
    require(report['protocol']['independent_context_per_task'] is True
            and report['protocol']['model_override'] is None, 'Unexpected evaluation protocol.')
    records = report['records']
    expected = {(case['id'], variant) for case in cases for variant in ('baseline', 'skill')}
    observed = {(row['case_id'], row['variant']) for row in records}
    require(observed == expected and len(records) == len(expected), 'Missing or duplicate evaluation record.')
    for row in records:
        case = case_map[row['case_id']]
        answer = row['response']['answer']
        require(isinstance(answer, str) and answer.strip(), 'Empty recorded answer.')
        references = row['response']['references_read']
        if row['variant'] == 'baseline':
            require(references == [], 'Baseline reports loading references.')
        else:
            require('skills/' + case['skill'] + '/SKILL.md' in references,
                    'Skill entrypoint missing from reported references.')
        for reference in references:
            source_text(root, reference)
        require(row['reference_snapshot'] == {name: report['snapshot']['skill_files_sha256'][name]
                                              for name in references},
                'Reported reference snapshot differs from the current package.')
        checks = row['judgment']['checks']
        require([check['index'] for check in checks] == list(range(len(case['checks']))),
                'Incomplete judgment checklist.')
        for check in checks:
            require(check['status'] in {'通过', '不通过', '无法确认'}, 'Unknown judgment status.')
            require(check['reason'], 'Missing judgment reason.')
            require(isinstance(check['evidence'], str) and check['evidence'] in answer,
                    'Judgment evidence is not in the recorded answer.')
    return {'cases': len(cases), 'records': len(records), 'snapshots_match': True,
            'judgments_are_review_not_accuracy_proof': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--snapshot', action='store_true')
    args = parser.parse_args()
    try:
        result = snapshot(args.root) if args.snapshot else validate(args.root)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'Evaluation validation failed: ' + str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False))
