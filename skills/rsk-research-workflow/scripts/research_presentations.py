"""Prepare and run pinned PPT Master tools in an explicit, retained task workspace."""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import uuid
from pathlib import Path

from presentation_source import adapt_mirror_checker, adapt_python, resource_path, source_rows


SKILL = Path(__file__).resolve().parents[1]
RESOURCE = SKILL / 'resources/presentation-engine'
LOCAL_TOOLS = frozenset({
    'project_manager.py', 'source_to_md.py', 'source_to_md/pdf_to_md.py',
    'source_to_md/doc_to_md.py', 'source_to_md/ppt_to_md.py', 'source_to_md/excel_to_md.py',
    'svg_quality_checker.py', 'finalize_svg.py', 'svg_to_pptx.py', 'pptx_to_svg.py',
    'pptx_intake.py', 'pptx_template_import.py', 'pptx_delivery_check.py',
    'beautify_inventory.py', 'beautify_identity.py', 'svg_authoring_view.py',
    'authoring_roundtrip.py', 'stamp_native_fallbacks.py', 'preset_shape_svg.py',
    'shape_boolean_svg.py', 'latex_render.py', 'animation_config.py',
    'pptx_animations.py', 'pptx_transitions.py', 'total_md_split.py',
    'template_preview_pptx.py', 'template_text_slots.py', 'apply_template.py',
    'register_template.py', 'update_spec.py', 'icon_sync.py', 'analyze_images.py',
    'slice_images.py', 'image_treat.py', 'visualization_recall.py',
    'visualization_catalog.py', 'chart_recall.py', 'pptx_effects.py',
    'pptx_gradients.py', 'powerpoint_video.py', 'video_subtitles.py',
    'video_sound_mix.py', 'video_motion_plan.py', 'narration_sync.py',
    'extract_svg_assets.py', 'extract_svg_pictures.py', 'text_measure.py',
    'slide_roster.py', 'visual_review.py', 'workflow_log.py',
    'mirror_template_materialize.py', 'check_annotations.py', 'check_spec_annotations.py',
    'compact_svg_coordinates.py', 'compact_svg_styles.py', 'batch_validate.py',
    'sound_sync.py', 'svg_compatibility.py', 'svg_position_calculator.py',
})
NETWORK_TOOLS = frozenset({'image_search.py', 'image_gen.py', 'notes_to_audio.py',
                           'source_to_md/web_to_md.py'})
SERVER_TOOLS = frozenset({'confirm_ui/server.py', 'spec_review/server.py', 'svg_editor/server.py'})


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def manifest():
    value = json.loads((RESOURCE / 'manifest.json').read_text(encoding='utf-8'))
    if (value['schema_version'] != 1 or value['source_commit'] !=
            '5e8856be0da8e6bc85c4aa28acc614478f7b7137' or value['pack'] != 'resources.json'):
        raise ValueError('Unexpected presentation resource identity.')
    return value


def verify():
    value = manifest()
    names = {row['path'] for row, data in source_rows(RESOURCE / value['pack'], value['pack_sha256'])}
    count = len(names)
    if count != value['resource_count']:
        raise ValueError('Presentation resource count mismatch.')
    routes = json.loads((SKILL / 'references/presentation-capabilities.json').read_text(encoding='utf-8'))
    if routes['source_commit'] != value['source_commit']:
        raise ValueError('Presentation routes refer to another source version.')
    required = {'SKILL.md', 'LICENSE', 'SPONSORS.md', 'SPONSORS_CN.md', 'workflows/routing.md'}
    required.update('scripts/' + name for name in LOCAL_TOOLS | NETWORK_TOOLS | SERVER_TOOLS)
    for section in ('routes', 'profiles', 'supporting_authorities'):
        required.update(routes[section].values())
    if required - names:
        raise ValueError('Missing presentation resources: ' + ', '.join(sorted(required - names)))
    return {'source_commit': value['source_commit'], 'source_version': value['source_version'],
            'resource_files': count, 'content_verified': True, 'execution_verified': False}


def checked_work(value):
    path = Path(value).expanduser()
    if '..' in path.parts or not path.is_absolute() or os.name == 'nt' and path.drive.upper() == 'C:':
        raise ValueError('Use an explicit non-C task directory, preferably D/E on Windows.')
    path = path.absolute()
    if path.is_relative_to(SKILL) or SKILL.is_relative_to(path):
        raise ValueError('The task directory must not overlap the installed skill.')
    for part in (path, *path.parents):
        if part.is_symlink() or (part.exists() and getattr(part.lstat(), 'st_file_attributes', 0)
                                 & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
            raise ValueError('Linked work directories are not supported.')
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


def environment(work):
    env = dict(os.environ)
    cache = work / '.rsk-cache'
    temp = work / '.rsk-tmp'
    for folder in (cache, temp):
        checked_work(folder)
    env.update(TEMP=str(temp), TMP=str(temp), TMPDIR=str(temp),
               XDG_CACHE_HOME=str(cache), MPLCONFIGDIR=str(cache / 'matplotlib'),
               PIP_CACHE_DIR=str(cache / 'pip'), PYTHONDONTWRITEBYTECODE='1',
               PYTHONUTF8='1', RSK_PRESENTATION_WORK_ROOT=str(work))
    return env


def runtime_check(runtime, work, receipt, full_check=True):
    if ('..' in runtime.parts or not runtime.is_absolute() or not runtime.is_relative_to(work)
            or not runtime.is_dir() or runtime.is_symlink() or
            receipt['pack_sha256'] != manifest()['pack_sha256']):
        raise ValueError('Unexpected prepared runtime path or source identity.')
    checked_work(runtime)
    for name, expected in receipt['files'].items():
        try:
            resource_path(name)
        except ValueError as error:
            raise ValueError('Prepared runtime changed; invalid receipt path: ' + str(name)) from error
        if (not full_check and Path(name).suffix.lower() in
                {'.svg', '.png', '.webp', '.wav', '.jpg', '.jpeg'}):
            continue
        path = runtime / name
        if not path.resolve().is_relative_to(runtime.resolve()) or path.is_symlink() or digest(path) != expected:
            raise ValueError('Prepared runtime changed; retain it and use a fresh task directory: ' + name)


def prepare(work, full_check=True, refresh=False):
    work = checked_work(work)
    value = manifest()
    state_path = work / '.rsk-presentation-runtime.json'
    if state_path.is_symlink() or (state_path.exists() and getattr(
            state_path.lstat(), 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
        raise ValueError('Linked presentation runtime receipt is not supported.')
    previous_state = state_path.read_bytes() if state_path.exists() else None
    binding = {name: digest(SKILL / 'scripts' / name) for name in
               ('presentation_source.py', 'presentation_retention.py', 'presentation_mirror.py')}
    if previous_state is not None and not refresh:
        receipt = json.loads(previous_state)
        if receipt['adaptation_sources'] != binding:
            raise ValueError('Runtime adapter changed; retain it and use prepare --refresh or a fresh task directory.')
        runtime = Path(receipt['runtime'])
        runtime_check(runtime, work, receipt, full_check=full_check)
        return receipt
    runtime = work / '.ppt-master-runtime' / (value['source_version'] + '-' + uuid.uuid4().hex[:12])
    checked_work(runtime)
    files, adapted = {}, []
    for row, data in source_rows(RESOURCE / value['pack'], value['pack_sha256']):
        result, calls = adapt_python(data) if row['path'].endswith('.py') else (data, 0)
        patches = []
        if row['path'] == 'scripts/svg_quality/checker.py':
            result = adapt_mirror_checker(result)
            patches.append('exact-unchanged-mirror-module-geometry-provenance')
        target = runtime / row['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(result)
        files[row['path']] = hashlib.sha256(result).hexdigest()
        if calls or patches:
            adapted.append({'path': row['path'], 'cleanup_calls_adapted': calls,
                            'functional_patches': patches,
                            'source_sha256': row['sha256'], 'sha256': files[row['path']]})
    if len(files) != value['resource_count']:
        raise ValueError('Incomplete prepared presentation package.')
    for local, deployed in (('presentation_retention.py', '_rsk_retention.py'),
                            ('presentation_mirror.py', '_rsk_mirror.py')):
        helper = runtime / 'scripts' / deployed
        with helper.open('xb') as stream:
            stream.write((SKILL / 'scripts' / local).read_bytes())
        files['scripts/' + deployed] = digest(helper)
    guard = subprocess.run([sys.executable, '-B', str(runtime / 'scripts/attribution_guard.py')],
                           cwd=work, env=environment(work), capture_output=True, text=True,
                           encoding='utf-8', timeout=30)
    if guard.returncode:
        raise ValueError('Upstream attribution guard failed; runtime retained without execution: ' + guard.stderr)
    receipt = {'schema_version': 1, 'runtime': str(runtime), 'source_commit': value['source_commit'],
               'pack_sha256': value['pack_sha256'], 'adaptation_sources': binding,
               'attribution_guard_passed': True, 'adapted_files': adapted, 'files': files,
               'cleanup_policy': 'retain temporary directories; rename superseded files, never delete'}
    encoded = (json.dumps(receipt, ensure_ascii=True, indent=2) + '\n').encode('utf-8')
    if previous_state is not None:
        if state_path.read_bytes() != previous_state:
            raise ValueError('Runtime receipt changed during preparation; both runtimes were retained.')
        history = checked_work(work / '.rsk-runtime-history')
        with (history / (uuid.uuid4().hex + '.json')).open('xb') as stream:
            stream.write(previous_state)
        staged_state = work / ('.rsk-runtime-state-' + uuid.uuid4().hex + '.json')
        with staged_state.open('xb') as stream:
            stream.write(encoded)
        os.replace(staged_state, state_path)
    else:
        with state_path.open('xb') as stream:
            stream.write(encoded)
    return receipt


def run_tool(tool, arguments, work, allow_network=False, allow_server=False):
    if tool not in LOCAL_TOOLS | NETWORK_TOOLS | SERVER_TOOLS:
        raise ValueError('Unknown presentation tool; repository updating is not a task capability.')
    if tool in NETWORK_TOOLS and not allow_network:
        raise ValueError('This tool needs the task-authorized --allow-network option.')
    if tool in SERVER_TOOLS and not allow_server:
        raise ValueError('Starting a local preview server needs --allow-server.')
    if not allow_network and any(str(arg).lower().startswith(('https://', 'http://')) for arg in arguments):
        raise ValueError('URL input requires task-authorized network access.')
    if tool == 'project_manager.py' and arguments:
        if arguments[0] == 'init' and '--dir' not in arguments:
            arguments += ['--dir', str(Path(work) / 'projects')]
        if arguments[0] == 'import-sources':
            if '--move' in arguments:
                raise ValueError('Keep original research materials; import copies instead.')
            if '--copy' not in arguments:
                arguments += ['--copy']
    if tool == 'svg_to_pptx.py' and arguments:
        options = {value.split('=', 1)[0] for value in arguments}
        motion = {'-t', '--transition', '--animation-config', '--recorded-narration',
                  '--inherit-motion-from', '--no-animations', '--roundtrip', '-h', '--help'}
        if not options & motion and not (Path(arguments[0]) / 'animations.json').is_file():
            arguments += ['-t', 'none']
    receipt = prepare(work, full_check=False)
    runtime = Path(receipt['runtime'])
    env = environment(Path(work))
    env['PYTHONPATH'] = os.pathsep.join([str(runtime / 'scripts'), str(runtime),
                                       *([env['PYTHONPATH']] if env.get('PYTHONPATH') else [])])
    completed = subprocess.run([sys.executable, '-B', str(SKILL / 'scripts/presentation_launch.py'),
                                str(runtime / 'scripts' / tool), *arguments],
                               cwd=Path(work), env=env)
    return completed.returncode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('verify')
    commands.add_parser('doctor')
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--work-dir', type=Path, required=True)
    prepare_parser.add_argument('--refresh', action='store_true',
                                help='Prepare a new runtime and retain the old runtime and receipt.')
    runner = commands.add_parser('run')
    runner.add_argument('--work-dir', type=Path, required=True)
    runner.add_argument('--allow-network', action='store_true')
    runner.add_argument('--allow-server', action='store_true')
    runner.add_argument('tool', choices=sorted(LOCAL_TOOLS | NETWORK_TOOLS | SERVER_TOOLS))
    runner.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        if args.command == 'run':
            arguments = args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments
            return run_tool(args.tool, arguments, checked_work(args.work_dir),
                            args.allow_network, args.allow_server)
        if args.command == 'prepare':
            result = prepare(args.work_dir, refresh=args.refresh)
            print(json.dumps({'runtime': result['runtime'], 'source_commit': result['source_commit'],
                              'resource_files': manifest()['resource_count'],
                              'adapted_files': len(result['adapted_files']),
                              'attribution_guard_passed': result['attribution_guard_passed'],
                              'receipt': str(Path(args.work_dir) / '.rsk-presentation-runtime.json')}))
        elif args.command == 'verify':
            print(json.dumps(verify()))
        else:
            print(json.dumps({'python': sys.version.split()[0],
                              'modules': {name: importlib.util.find_spec(name) is not None for name in
                                          ('pptx', 'xlsxwriter', 'yaml', 'PIL', 'pathops', 'uharfbuzz',
                                           'fitz', 'mammoth', 'openpyxl', 'edge_tts')},
                              'commands': {name: shutil.which(name) for name in ('ffmpeg', 'pandoc', 'soffice')},
                              'network_checked': False, 'model_calls': 0}))
    except (OSError, ValueError, KeyError, TypeError, SyntaxError) as error:
        parser.exit(1, 'Presentation tool: ' + str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
