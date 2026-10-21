"""Verify corpus metadata with an explicit, manuscript-bound prose reference join."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from research_engine import ENGINE, local_environment


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def load_inputs(passport_path, manuscript_path, join_path):
    import yaml
    from scripts.verify_submission_package import extract_ref_markers

    raw = {name: Path(path).read_bytes() for name, path in (
        ('passport', passport_path), ('manuscript', manuscript_path), ('join', join_path))}
    passport = yaml.safe_load(raw['passport'])
    join = json.loads(raw['join'])
    if not isinstance(passport, dict) or not isinstance(join, dict):
        raise ValueError('Passport and reference join must be objects.')
    if set(join) != {'schema', 'manuscript_sha256', 'ref_slug_by_key'} or (
            join['schema'] != 'rsk.citation-join.v1' or
            join['manuscript_sha256'] != sha256(raw['manuscript'])):
        raise ValueError('Reference join is not bound to the current manuscript bytes.')
    corpus = passport.get('literature_corpus')
    if not isinstance(corpus, list) or not corpus:
        raise ValueError('A nonempty literature_corpus is required.')
    keys = [row.get('citation_key') for row in corpus if isinstance(row, dict)]
    if len(keys) != len(corpus) or any(not isinstance(key, str) or not key for key in keys) or (
            len(set(keys)) != len(keys)):
        raise ValueError('Corpus citation keys must be nonempty and unique.')
    mapping = join['ref_slug_by_key']
    slugs = extract_ref_markers({'manuscript': raw['manuscript'].decode('utf-8')})
    if (not isinstance(mapping, dict) or set(mapping) != set(keys) or
            any(not isinstance(slug, str) or slug not in slugs for slug in mapping.values()) or
            len(set(mapping.values())) != len(mapping)):
        raise ValueError('Every corpus key needs a unique reference marker actually present in the manuscript.')
    return passport, mapping, {name + '_sha256': sha256(value) for name, value in raw.items()}


def verify(passport_path, manuscript_path, join_path, work_dir, *,
           allow_metadata_network=False, no_cache=False, clients_factory=None):
    if not allow_metadata_network:
        raise ValueError('Metadata lookup requires the task-authorized --allow-metadata-network option.')
    work, _env = local_environment(work_dir)
    for path in (ENGINE, ENGINE / 'scripts'):
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from scripts.verify_passport import _real_clients
    from scripts.verification_gate import verify_passport
    from scripts.verification_cache import VerificationCache
    from scripts.check_literature_corpus_schema import (
        validate_passport, load_schema, ENTRY_SCHEMA_PATH,
        TERMINAL_POLICIES_SCHEMA_PATH, SIGNAL_SCHEMA_PATH)

    passport, mapping, hashes = load_inputs(passport_path, manuscript_path, join_path)
    errors = validate_passport(Path(passport_path), load_schema(ENTRY_SCHEMA_PATH),
                               load_schema(TERMINAL_POLICIES_SCHEMA_PATH),
                               load_schema(SIGNAL_SCHEMA_PATH))
    if errors:
        raise ValueError('Invalid literature corpus: ' + '; '.join(map(str, errors)))
    if sha256(Path(passport_path).read_bytes()) != hashes['passport_sha256']:
        raise ValueError('Passport changed during validation.')
    cache_path = work / '.rsk-cache' / 'verification.db'
    cache = None if no_cache else VerificationCache(cache_path)
    outcomes = verify_passport(passport, clients=(clients_factory or _real_clients)(),
                               ref_slug_by_key=mapping, cache=cache,
                               revalidate_stale=False)
    return {'schema': 'rsk.citation-lookup.v1', 'inputs': hashes,
            'join_source': 'explicit_mapping_checked_against_manuscript_markers',
            'verification_scope': 'bibliographic_lookup_not_claim_support_or_reading',
            'anchor_verification': 'not_checked', 'cache_path': None if no_cache else str(cache_path),
            'citation_verification_summary': outcomes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('passport', 'manuscript', 'join', 'work-dir'):
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--allow-metadata-network', action='store_true')
    parser.add_argument('--no-cache', action='store_true')
    parser.add_argument('--output', type=Path,
                        help='New JSON file inside the selected work directory; otherwise stdout.')
    args = parser.parse_args()
    try:
        work, _ = local_environment(args.work_dir)
        if args.output and (not args.output.is_absolute() or
                            not args.output.absolute().is_relative_to(work) or args.output.exists()):
            raise ValueError('--output must be a new absolute path inside --work-dir.')
        result = verify(args.passport, args.manuscript, args.join, work,
                        allow_metadata_network=args.allow_metadata_network, no_cache=args.no_cache)
        data = json.dumps(result, ensure_ascii=True, indent=2) + '\n'
        if args.output:
            with args.output.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(data)
        else:
            print(data, end='')
    except (ValueError, OSError, TypeError, ImportError) as error:
        parser.exit(1, 'Citation lookup failed: ' + str(error) + '\n')


if __name__ == '__main__':
    main()
