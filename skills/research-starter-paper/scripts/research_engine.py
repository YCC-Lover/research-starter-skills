"""Locate and verify the bundled research workflows without running model tasks."""

import argparse
import hashlib
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path, PurePosixPath


SKILL = Path(__file__).resolve().parents[1]
ENGINE = SKILL / 'resources/research-engine'
CATALOG = SKILL / 'references/advanced-capabilities.json'

# Deliberate local-only entrypoints. Provider dispatch and maintenance scripts
# are not enabled merely because they are present in the source snapshot.
LOCAL_COMMANDS = {
    'scripts/check_acronyms.py',
    'scripts/check_revision_token_conservation.py',
    'scripts/check_experiment_provenance.py',
    'scripts/check_repro_lock.py',
    'scripts/check_literature_corpus_schema.py',
    'scripts/check_compliance_report.py',
    'scripts/check_sprint_contract.py',
    'scripts/check_phase_conformance.py',
    'scripts/check_panel_synthesis.py',
    'scripts/check_re_review_synthesis.py',
    'scripts/check_claim_audit_consistency.py',
    'scripts/check_committee_correspondence.py',
    'scripts/claim_registry_coverage.py',
    'scripts/claim_strength_drift_disposition.py',
    'scripts/evidence_rows.py',
    'scripts/run_ledger.py',
    'scripts/ars_mark_read.py',
    'scripts/human_read_attestation_resolver.py',
    'scripts/ars_anchorize_draft.py',
    'scripts/ars_apply_revision_patch.py',
    'scripts/revision_roadmap.py',
    'scripts/research_workflow_profile.py',
    'scripts/resolve_review_target_context.py',
    'scripts/review_criteria_binding.py',
    'scripts/build_submission_packet_manifest.py',
    'scripts/inquiry_branch_ledger.py',
    'scripts/adjudication_activity.py',
    'scripts/review_panel_provenance.py',
    'scripts/verify_submission_package.py',
    'scripts/recompute_receipts.py',
    'scripts/cross_model_handoff.py',
    'sr-screener/scripts/prepare_records.py',
    'sr-screener/scripts/prepare_fulltext.py',
    'sr-screener/scripts/build_workflow.py',
    'sr-screener/scripts/merge_decisions.py',
    'sr-screener/scripts/build_outputs.py',
}
WINDOWS_313_COMMANDS = {
    'scripts/inquiry_branch_ledger.py', 'scripts/review_criteria_binding.py',
    'scripts/build_submission_packet_manifest.py', 'scripts/adjudication_activity.py',
}


def safe_file(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Expected a relative resource path.')
    name = PurePosixPath(relative)
    if name.is_absolute() or '..' in name.parts:
        raise ValueError('Resource path must stay inside the bundle.')
    path = root / relative
    if not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError('Missing or escaping resource: ' + relative)
    for part in (path, *path.parents):
        if part == root.parent:
            break
        attributes = getattr(part.lstat(), 'st_file_attributes', 0)
        if part.is_symlink() or attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
            raise ValueError('Linked resource: ' + relative)
    return path


def load_catalog():
    data = json.loads(CATALOG.read_text(encoding='utf-8'))
    ids = [row['id'] for row in data['modes']]
    if len(set(ids)) != data['mode_count'] or len(ids) != data['mode_count']:
        raise ValueError('Mode inventory count or uniqueness mismatch.')
    for row in data['modes']:
        if row['id'] != row['workflow'] + ':' + row['mode']:
            raise ValueError('Malformed mode identity.')
        safe_file(ENGINE, row['entry'])
    for route in data['additional_role_routes']:
        for resource in route['resources']:
            safe_file(ENGINE, resource)
    return data


def resolve_mode(workflow, mode):
    catalog = load_catalog()
    matches = [row for row in catalog['modes'] if row['workflow'] == workflow and row['mode'] == mode]
    if len(matches) != 1:
        raise ValueError('Unknown workflow/mode. Use modes to inspect supported identifiers.')
    row = matches[0]
    return {**row, 'entry_path': str(safe_file(ENGINE, row['entry'])),
            'resource_root': str(ENGINE),
            'adapter_guide': str(SKILL / 'references/advanced-research.md'),
            'execution': 'not_started',
            'next_step': 'Read the adapter and selected workflow, then its mode-specific role '
                         'contracts. Resource discovery does not execute or verify a research task.'}


def verify_bundle():
    manifest = json.loads((ENGINE / 'source-manifest.json').read_text(encoding='utf-8'))
    catalog = load_catalog()
    if manifest['source_commit'] != catalog['source_commit']:
        raise ValueError('Mode inventory and source snapshot differ.')
    patches_path = SKILL / 'references/research-engine-patches.json'
    patches = json.loads(patches_path.read_text(encoding='utf-8')) if patches_path.exists() else {'files': []}
    changes = {row['path']: row for row in patches['files']}
    if len(changes) != len(patches['files']):
        raise ValueError('Duplicate runtime patch record.')
    names = set()
    empty_fixtures = []
    for row in manifest['files']:
        name = row['path']
        if name in names:
            raise ValueError('Duplicate runtime resource: ' + name)
        names.add(name)
        data = safe_file(ENGINE, name).read_bytes()
        expected = row['sha256']
        if name in changes:
            patch = changes[name]
            if patch['base_sha256'] != expected or not patch.get('reason'):
                raise ValueError('Runtime patch lacks its source binding: ' + name)
            expected = patch['sha256']
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError('Runtime content checksum mismatch: ' + name)
        if name.startswith('scripts/adapters/examples/folder_scan/input_fixture/') and name.endswith('.pdf'):
            if data:
                raise ValueError('The folder-scan examples must be empty filename fixtures.')
            empty_fixtures.append(name)
    if set(changes) - names:
        raise ValueError('Runtime patch references a file outside the source inventory.')
    expected_files = names | {'source-manifest.json'}
    observed_files = {p.relative_to(ENGINE).as_posix() for p in ENGINE.rglob('*') if p.is_file()}
    if observed_files != expected_files:
        raise ValueError('Unregistered or missing runtime files: ' + ', '.join(sorted(observed_files ^ expected_files)))
    if manifest.get('license') != 'CC-BY-NC-4.0' or 'LICENSE' not in names:
        raise ValueError('Missing source license.')
    for command in LOCAL_COMMANDS:
        safe_file(ENGINE, command)
    return {'resource_files': len(names), 'modes': len(catalog['modes']),
            'source_commit': manifest['source_commit'], 'content_verified': True,
            'empty_pdf_filename_fixtures': empty_fixtures,
            'execution_verified': False}


def doctor():
    modules = {}
    for name in ('yaml', 'jsonschema', 'requests', 'numpy', 'pymupdf', 'pypdf'):
        try:
            modules[name] = importlib.util.find_spec(name) is not None
        except (ModuleNotFoundError, ValueError):
            modules[name] = False
    return {'bundle': verify_bundle(), 'python': sys.version.split()[0],
            'optional_modules': modules, 'network_checked': False, 'model_calls': 0,
            'limits': 'Resource integrity and dependency discovery only; '
                      'not a model evaluation or proof of external tool availability.'}


def local_environment(work_dir):
    work = Path(work_dir).expanduser()
    if not work.is_absolute():
        raise ValueError('--work-dir must be an explicit absolute directory.')
    if os.name == 'nt' and work.drive.upper() == 'C:':
        raise ValueError('Use a D/E task directory for intermediate files, not C.')
    work = work.absolute()
    if work.is_relative_to(SKILL) or SKILL.is_relative_to(work):
        raise ValueError('The work directory must not overlap the installed skill.')
    for part in (work, *work.parents):
        if part.is_symlink():
            raise ValueError('Linked work directory is not supported.')
        if part.exists():
            attributes = getattr(part.lstat(), 'st_file_attributes', 0)
            if attributes & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0):
                raise ValueError('Reparse-point work directory is not supported.')
    work.mkdir(parents=True, exist_ok=True)
    temp = work / '.rsk-tmp'
    cache = work / '.rsk-cache'
    for folder in (temp, cache):
        if folder.is_symlink() or (folder.exists() and (
                not folder.is_dir() or getattr(folder.lstat(), 'st_file_attributes', 0)
                & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0))):
            raise ValueError('Unsafe runtime directory: ' + str(folder))
        folder.mkdir(exist_ok=True)
    env = dict(os.environ)
    env.update({'TEMP': str(temp), 'TMP': str(temp), 'TMPDIR': str(temp),
                'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1',
                'ARS_VERIFICATION_CACHE_PATH': str(cache / 'verification.db'),
                'XDG_CACHE_HOME': str(cache), 'MPLCONFIGDIR': str(cache / 'matplotlib'),
                'PIP_CACHE_DIR': str(cache / 'pip'), 'ARS_UPDATE_CHECK': '0'})
    env['PYTHONPATH'] = os.pathsep.join([str(ENGINE), str(ENGINE / 'scripts'),
                                       *([env['PYTHONPATH']] if env.get('PYTHONPATH') else [])])
    return work, env


def run_local(relative, arguments, work_dir):
    if relative not in LOCAL_COMMANDS:
        raise ValueError('Not a supported local entrypoint. Network/model and maintenance '
                         'commands require a separate explicit execution path.')
    if os.name == 'nt' and relative in WINDOWS_313_COMMANDS and sys.version_info < (3, 13):
        raise ValueError('Use Python 3.13+ for the native Windows research transaction helpers.')
    script = safe_file(ENGINE, relative)
    work, env = local_environment(work_dir)
    # This is environment preparation, not a filesystem/network sandbox. The
    # caller must still inspect task-specific outputs and authorization contracts.
    result = subprocess.run([sys.executable, '-B', str(script), *arguments], cwd=work, env=env)
    return result.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    modes = commands.add_parser('modes')
    modes.add_argument('--skill')
    resolve = commands.add_parser('resolve')
    resolve.add_argument('workflow')
    resolve.add_argument('mode')
    commands.add_parser('verify')
    commands.add_parser('doctor')
    runner = commands.add_parser('run-local')
    runner.add_argument('--work-dir', required=True, type=Path)
    runner.add_argument('script', choices=sorted(LOCAL_COMMANDS))
    runner.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.command == 'run-local':
            arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
            return run_local(args.script, arguments, args.work_dir)
        if args.command == 'modes':
            catalog = load_catalog()
            result = [row for row in catalog['modes'] if not args.skill or args.skill in row['skills']]
            if args.skill and not result:
                roles = [r for r in catalog['additional_role_routes'] if r['skill'] == args.skill]
                if not roles:
                    raise ValueError('Unknown skill owner.')
                result = roles
        elif args.command == 'resolve':
            result = resolve_mode(args.workflow, args.mode)
        else:
            result = doctor() if args.command == 'doctor' else verify_bundle()
        print(json.dumps(result, ensure_ascii=True, indent=2))
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(1, 'Research engine check failed: ' + str(error) + '\n')


if __name__ == '__main__':
    raise SystemExit(main())
