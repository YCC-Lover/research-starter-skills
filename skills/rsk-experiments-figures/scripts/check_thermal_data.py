"""Read-only checks and optional NumPy differentiation of exported TG data."""

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def number(value, location):
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError('Expected a number at ' + location) from error
    if not math.isfinite(result):
        raise ValueError('Non-finite value at ' + location)
    return result


def check_data(path, metadata=None, derive=False):
    path = Path(path)
    if path.suffix.lower() != '.csv':
        raise ValueError('Use a readable CSV export; this tool does not parse Origin/XLSX files.')
    raw = path.read_bytes()
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.DictReader(handle)
        names = reader.fieldnames or []
        if not names or len(names) != len(set(names)) or any(not name for name in names):
            raise ValueError('Missing, empty or duplicate CSV column names.')
        records = list(reader)
    if len(records) < 2:
        raise ValueError('At least two rows are needed.')
    if any(None in row or any(value is None for value in row.values()) for row in records):
        raise ValueError('CSV row length differs from the header.')
    config = metadata or {}
    if not isinstance(config, dict):
        raise ValueError('Metadata must be an object.')
    temperature_name = config.get('temperature_column', 'temperature_C')
    if temperature_name not in names:
        raise ValueError('Temperature column is missing: ' + str(temperature_name))
    mass_names = [name for name in names if name != temperature_name]
    if not mass_names:
        raise ValueError('At least one mass column is needed.')
    if 'mass_unit' not in config and any(not name.endswith('_pct') for name in mass_names):
        raise ValueError('Mass units must be explicit in metadata or use *_pct column names.')
    if temperature_name != 'temperature_C' and 'temperature_unit' not in config:
        raise ValueError('Temperature units must be explicit for a custom column name.')
    if config.get('temperature_unit', 'C') != 'C' or config.get('mass_unit', '%') != '%':
        raise ValueError('This schema requires temperature in C and mass in percent; no implicit conversion.')
    temperature = [number(row[temperature_name], 'row ' + str(i + 2) + ', ' + temperature_name)
                   for i, row in enumerate(records)]
    if any(right <= left for left, right in zip(temperature, temperature[1:])):
        raise ValueError('Temperature must be strictly increasing; no sorting or duplicate removal is performed.')
    samples = config.get('samples', {})
    if not isinstance(samples, dict):
        raise ValueError('samples metadata must be an object.')
    if any(name not in mass_names for name in samples):
        raise ValueError('Metadata names a mass column not present in the CSV.')
    np = None
    if derive:
        try:
            import numpy as np
        except ImportError as error:
            raise ValueError('--derive needs NumPy; no packages have been installed.') from error
    conditions = ('sample_id', 'atmosphere', 'flow_ml_min', 'heating_rate_C_min',
                  'initial_mass_mg', 'normalization', 'independent_repeats')
    comparison_fields = ('atmosphere', 'flow_ml_min', 'heating_rate_C_min', 'normalization')
    output = []
    for name in mass_names:
        values = [number(row[name], 'row ' + str(i + 2) + ', ' + name)
                  for i, row in enumerate(records)]
        details = samples.get(name, {})
        if not isinstance(details, dict):
            raise ValueError('Each sample metadata entry must be an object.')
        details = dict(details)
        for field in ('sample_id', 'atmosphere', 'normalization'):
            if details.get(field) is not None and not isinstance(details[field], str):
                raise ValueError('Expected text or null at ' + name + '.' + field)
        for field in ('flow_ml_min', 'heating_rate_C_min', 'initial_mass_mg', 'independent_repeats'):
            if details.get(field) is not None:
                value = number(details[field], name + '.' + field)
                if value <= 0 or (field == 'independent_repeats' and not value.is_integer()):
                    raise ValueError('Invalid positive measurement or repeat count at ' + name + '.' + field)
                details[field] = value
        entry = {'column': name, 'points': len(values),
                 'first_mass_pct': values[0], 'last_mass_pct': values[-1],
                 'last_temperature_C': temperature[-1],
                 'missing_metadata': [field for field in conditions if details.get(field) in (None, '')],
                 'conditions': {field: details.get(field) for field in conditions},
                 'warnings': ['Mass outside 0..100%; verify definition and calibration.']
                 if any(value < 0 or value > 100 for value in values) else []}
        if derive:
            derivative = -np.gradient(values, temperature, edge_order=1)
            entry['derivative'] = {'definition': '-d(mass%)/dT', 'unit': '%/C',
                                   'method': 'numpy.gradient(edge_order=1)',
                                   'numpy_version': np.__version__, 'smoothing': None,
                                   'values': derivative.tolist()}
        output.append(entry)
    mismatches, unknown = [], []
    for field in comparison_fields:
        values = [entry['conditions'][field] for entry in output]
        if any(value in (None, '') for value in values):
            unknown.append(field)
        elif any(value != values[0] for value in values[1:]):
            mismatches.append(field)
    return {'input_name': path.name, 'input_sha256': hashlib.sha256(raw).hexdigest(),
            'data_kind': config.get('data_kind', 'not-verified'),
            'temperature_unit': 'C', 'mass_unit': '%',
            'temperature_range_C': [temperature[0], temperature[-1]],
            'samples': output, 'comparison': {'different_conditions': mismatches,
                                             'unknown_conditions': unknown,
                                             'causal_or_statistical_conclusion': 'not-assessed'},
            'derived': derive, 'files_written': 0,
            'limits': ['Sampling points are not independent repeats.',
                       'Endpoint mass is defined only at the reported temperature.',
                       'No mechanism, significance or thermal-stability ranking is inferred.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--metadata', type=Path)
    parser.add_argument('--derive', action='store_true', help='Explicitly calculate -d(mass%)/dT; requires NumPy.')
    args = parser.parse_args()
    try:
        metadata = json.loads(args.metadata.read_text(encoding='utf-8')) if args.metadata else None
        result = check_data(args.csv, metadata, args.derive)
        if args.metadata:
            result['metadata_sha256'] = hashlib.sha256(args.metadata.read_bytes()).hexdigest()
    except (ValueError, OSError, TypeError) as error:
        parser.exit(1, 'Thermal check failed: ' + str(error) + '\n')
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
