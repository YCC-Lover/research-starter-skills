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


def capture_sources(root, cases_path='evals/cases.json'):
    root = Path(root).resolve()
    cases = json.loads(source_text(root, cases_path))
    inputs = {name: source_text(root, name) for case in cases['cases'] for name in case['files']}
    skills = {path.relative_to(root).as_posix(): source_text(root, path.relative_to(root).as_posix())
              for path in sorted((root / 'skills').rglob('*')) if path.is_file()}
    return {'cases': cases, 'inputs': inputs, 'skills': skills}


def source_snapshot(sources):
    cases, inputs, skills = sources['cases'], sources['inputs'], sources['skills']
    return {'cases_sha256': digest(cases), 'inputs_sha256': digest(inputs),
            'skills_sha256': digest(skills),
            'skill_files_sha256': {name: hashlib.sha256(text.encode('utf-8')).hexdigest()
                                   for name, text in skills.items()}}


def snapshot(root, cases_path='evals/cases.json'):
    return source_snapshot(capture_sources(root, cases_path))


def valid_relative(name):
    require(isinstance(name, str) and name and '\\' not in name
            and not Path(name).is_absolute() and ':' not in name
            and '..' not in Path(name).parts, 'Unsafe evaluation source path.')


def case_variants(case):
    variants = case.get('variants', ['baseline', 'skill'])
    require(isinstance(variants, list) and variants and
            all(isinstance(value, str) and value in {'baseline', 'skill'} for value in variants)
            and len(set(variants)) == len(variants), 'Invalid evaluation variants.')
    return variants


def validate_run(report, sources):
    archived_cases = sources['cases']['cases']
    case_map = {case['id']: case for case in archived_cases}
    require(len(case_map) == len(archived_cases) and archived_cases, 'Duplicate or empty evaluation cases.')
    selection = report.get('case_ids', list(case_map))
    require(isinstance(selection, list) and selection and
            all(isinstance(name, str) and name in case_map for name in selection)
            and len(set(selection)) == len(selection), 'Invalid selected evaluation cases.')
    cases = [case_map[name] for name in selection]
    for group in ('inputs', 'skills'):
        require(isinstance(sources[group], dict), 'Invalid archived source map.')
        for name, value in sources[group].items():
            valid_relative(name)
            require(isinstance(value, str), 'Archived source is not text.')
    require(set(sources['inputs']) == {name for case in archived_cases for name in case['files']},
            'Archived input set differs from cases.')
    require(report['snapshot'] == source_snapshot(sources), 'Archived source snapshot changed.')
    require(report['protocol']['independent_context_per_task'] is True, 'Unexpected evaluation protocol.')
    records = report['records']
    for case in cases:
        require(type(case.get('repetitions', 1)) is int and case.get('repetitions', 1) > 0,
                'Invalid repetition count.')
    expected = {(case['id'], variant, repetition) for case in cases
                for variant in case_variants(case) for repetition in range(1, case.get('repetitions', 1) + 1)}
    observed = {(row['case_id'], row['variant'], row.get('repetition', 1)) for row in records}
    require(observed == expected and len(records) == len(expected), 'Missing or duplicate evaluation record.')
    guided_contexts = set()
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
            valid_relative(reference)
            require(reference in sources['skills'], 'Reported reference missing from archived sources.')
        require(row['reference_snapshot'] == {name: report['snapshot']['skill_files_sha256'][name]
                                              for name in references},
                'Reported reference snapshot differs from the current package.')
        checks = row['judgment']['checks']
        validate_checks(checks, case, answer)
        if sources['cases'].get('grading', {}).get('type') == 'guided-deliverable-v1':
            turns = row['response']['turns']
            require(isinstance(turns, list) and turns, 'Missing guided conversation.')
            require(all(isinstance(turn.get('user'), str) and turn['user'] and
                        isinstance(turn.get('answer'), str) and turn['answer'] and
                        turn['answer'] in answer and isinstance(turn.get('context_id'), str)
                        and turn['context_id'] for turn in turns), 'Invalid guided conversation turn.')
            contexts = {turn['context_id'] for turn in turns}
            require(not contexts.intersection(guided_contexts), 'Guided task contexts were reused.')
            guided_contexts.update(contexts)
            first_input = sources['inputs'][case['files'][0]].strip()
            require(turns[0]['user'] == first_input, 'Guided first input differs from the fixed request.')
            resume_inputs = [name for name in case['files'] if name.endswith('/resume.md')]
            if resume_inputs:
                require(len(turns) == 3 and turns[0]['context_id'] == turns[1]['context_id']
                        and turns[2]['context_id'] != turns[0]['context_id'],
                        'Guided resumption requires a fresh context after the initial exchange.')
                require(turns[2]['user'] == sources['inputs'][resume_inputs[0]].strip(),
                        'Guided resume request differs from the fixed request.')
                require(turns[1]['user'] == sources['inputs'][case['files'][1]].strip(),
                        'Guided followup differs from the fixed request.')
            student_inputs = [name for name in case['files'] if name.endswith('/student-answer.md')]
            if student_inputs:
                require(len(turns) == 2 and turns[0]['context_id'] == turns[1]['context_id'] and
                        turns[1]['user'] == sources['inputs'][student_inputs[0]].strip(),
                        'Guided student answer differs from the fixed request.')
        if sources['cases'].get('grading', {}).get('type') == 'anchored-utility-v1':
            judgments = row['independent_judgments']
            require(len(judgments) == 2 and len({j['grader_id'] for j in judgments}) == 2,
                    'Expected two independent utility judgments.')
            require({j['pass'] for j in judgments} == {1, 2}, 'Missing order-check judgment pass.')
            for judgment in judgments:
                validate_checks(judgment['checks'], case, answer)
                for check in judgment['checks']:
                    require(type(check['score']) is int and check['score'] in range(4),
                            'Invalid anchored utility score.')
                if judgment.get('factual_errors'):
                    require(judgment['checks'][1]['score'] == 0, 'Factual error scoring mismatch.')
            for i, check in enumerate(checks):
                require(check['score'] == sum(j['checks'][i]['score'] for j in judgments) / 2,
                        'Utility mean score mismatch.')
            if case.get('followup_file'):
                require(row['response']['followup_input'] == sources['inputs'][case['followup_file']],
                        'Follow-up material differs between recorded tasks.')
                require(len(row['response']['turns']) == 2 and
                        row['response']['turns'][1]['answer'] == answer,
                        'Incomplete multi-turn response.')
    return cases


def validate_checks(checks, case, answer):
    require([check['index'] for check in checks] == list(range(len(case['checks']))),
            'Incomplete judgment checklist.')
    for check in checks:
        require(check['status'] in {'通过', '不通过', '无法确认'}, 'Unknown judgment status.')
        require(check['reason'], 'Missing judgment reason.')
        require(isinstance(check['evidence'], str) and check['evidence'] in answer,
                'Judgment evidence is not in the recorded answer.')
        require(check['evidence'] or check['status'] == '无法确认', 'Missing judgment evidence.')


def run_impact(root, item, report, sources):
    current_cases = json.loads(source_text(root, item['cases']))['cases']
    current_map = {case['id']: case for case in current_cases}
    recorded_map = {case['id']: case for case in sources['cases']['cases']}
    if 'case_ids' in report:
        selected = set(report['case_ids'])
        current_map = {key: value for key, value in current_map.items() if key in selected}
        recorded_map = {key: value for key, value in recorded_map.items() if key in selected}
    affected = []
    for case_id in sorted(set(current_map) | set(recorded_map)):
        old = recorded_map.get(case_id)
        new = current_map.get(case_id)
        reasons = []
        if old != new:
            reasons.append('case definition changed')
        if old:
            dependencies = set(old.get('dependencies', []))
            dependencies.update(name for row in report['records'] if row['case_id'] == case_id
                                for name in row['response']['references_read'])
            for name in old['files']:
                try:
                    current = source_text(root, name)
                except OSError:
                    current = None
                if current != sources['inputs'].get(name):
                    reasons.append('input changed: ' + name)
            for name in sorted(dependencies):
                valid_relative(name)
                try:
                    current = source_text(root, name)
                except OSError:
                    current = None
                if current != sources['skills'].get(name):
                    reasons.append('dependency changed: ' + name)
        if reasons:
            affected.append({'case_id': case_id, 'reasons': reasons})
    return affected


def validate(root=ROOT, impact_only=False):
    root = Path(root).resolve()
    index = json.loads(source_text(root, 'evals/runs.json'))
    require(index['schema_version'] == 2, 'Unknown evaluation index schema.')
    runs = index['runs']
    require(runs and len({item['id'] for item in runs}) == len(runs), 'Duplicate or empty run index.')
    catalog = json.loads(source_text(root, 'catalog.json'))
    results, covered, count, records, expected_records = [], set(), 0, 0, 0
    for item in runs:
        require(item['state'] in {'historical', 'current'}, 'Unknown run state.')
        for field in ('report', 'sources', 'cases'):
            valid_relative(item[field])
        report = json.loads(source_text(root, item['report']))
        sources = json.loads(source_text(root, item['sources']))
        cases = validate_run(report, sources)
        affected = []
        if item['state'] == 'current':
            require(report['package_version'] == catalog['version'], 'Evaluation package version mismatch.')
            affected = run_impact(root, item, report, sources)
            covered.update(case['id'] for case in cases)
        count += len(cases)
        records += len(report['records'])
        expected_records += sum(case.get('repetitions', 1) * len(case_variants(case)) for case in cases)
        results.append({'id': item['id'], 'state': item['state'], 'cases': len(cases),
                        'records': len(report['records']), 'affected_cases': affected})
    required = index['required_current_cases']
    require(len(required) == len(set(required)), 'Duplicate required case IDs.')
    missing = sorted(set(required) - covered)
    if not impact_only:
        require(not missing, 'Missing current behavior cases: ' + ', '.join(missing))
        require(not any(run['affected_cases'] for run in results),
                'Evaluation inputs or dependency snapshot changed; use --impact and re-evaluate affected cases.')
    return {'cases': count, 'records': records, 'expected_records': expected_records, 'archived_snapshots_match': True,
            'current_cases_recorded': len(covered),
            'behavior_status': 'current-records-present-not-accuracy-proof' if covered
            else 'historical-only-no-current-model-run',
            'required_current_cases_missing': missing, 'runs': results,
            'judgments_are_review_not_accuracy_proof': True}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--snapshot', action='store_true')
    parser.add_argument('--sources', action='store_true', help='Print full source capture; does not run a model.')
    parser.add_argument('--cases', default='evals/cases.json', help='Repository-relative cases path for source capture.')
    parser.add_argument('--impact', action='store_true', help='Report changed current-case dependencies without refreshing records.')
    args = parser.parse_args()
    try:
        if args.snapshot or args.sources:
            result = capture_sources(args.root, args.cases) if args.sources else snapshot(args.root, args.cases)
        else:
            result = validate(args.root, impact_only=args.impact)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, 'Evaluation validation failed: ' + str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False))
