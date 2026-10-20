import importlib.util
import hashlib
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('thermal', ROOT / 'skills/rsk-experiments-figures/scripts/check_thermal_data.py')
THERMAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(THERMAL)


class ThermalTests(unittest.TestCase):
    def test_public_tool_record_matches_distributed_sources(self):
        report = json.loads((ROOT / 'examples/worked/thermal-check.json').read_text(encoding='utf-8'))
        script = ROOT / report['command'][1]
        self.assertEqual(hashlib.sha256(script.read_bytes()).hexdigest(), report['script_sha256'])
        for field, name in [('input_sha256', 'thermal.csv'), ('metadata_sha256', 'thermal.json')]:
            with self.subTest(file=name):
                self.assertEqual(hashlib.sha256((ROOT / 'examples/worked' / name).read_bytes()).hexdigest(),
                                 report['stdout_json'][field])

    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix='rsk-thermal-'))
        self.data = self.work / 'input.csv'
        self.data.write_text('temperature_C,A_pct,B_pct\n0,100,100\n1,98,99\n3,94,97\n', encoding='utf-8')

    def test_default_is_read_only_and_does_not_derive(self):
        before = self.data.read_bytes()
        result = THERMAL.check_data(self.data)
        self.assertFalse(result['derived'])
        self.assertNotIn('derivative', result['samples'][0])
        self.assertEqual(result['files_written'], 0)
        self.assertEqual(before, self.data.read_bytes())
        self.assertTrue(result['comparison']['unknown_conditions'])
        self.assertEqual(len(list(self.work.iterdir())), 1)

    def test_gradient_uses_actual_uneven_temperature_grid(self):
        result = THERMAL.check_data(self.data, derive=True)
        for value in result['samples'][0]['derivative']['values']:
            self.assertAlmostEqual(value, 2.0)
        self.assertEqual(result['samples'][0]['derivative']['unit'], '%/C')
        self.assertEqual(result['samples'][0]['last_temperature_C'], 3)

    def test_confounded_conditions_are_reported(self):
        result = THERMAL.check_data(self.data, {'samples': {
            'A_pct': {'atmosphere': 'nitrogen', 'heating_rate_C_min': 10},
            'B_pct': {'atmosphere': 'air', 'heating_rate_C_min': 20}}})
        self.assertEqual(result['comparison']['different_conditions'], ['atmosphere', 'heating_rate_C_min'])
        self.assertEqual(result['comparison']['causal_or_statistical_conclusion'], 'not-assessed')

    def test_invalid_rows_fail_without_silent_repair(self):
        for text in ('temperature_C,A_pct\n0,100\n0,98\n',
                     'temperature_C,A_pct\n1,100\n0,98\n',
                     'temperature_C,A_pct\n0,100\n1,nan\n',
                     'temperature_C,A_pct\n0,100\n1,\n',
                     'temperature_C,A_pct,A_pct\n0,100,100\n1,98,99\n',
                     'temperature_C,A_pct\n0,100,5\n1,98\n'):
            with self.subTest(text=text):
                self.data.write_text(text, encoding='utf-8')
                with self.assertRaises(ValueError):
                    THERMAL.check_data(self.data)
                self.assertEqual(self.data.read_text(encoding='utf-8'), text)

    def test_unknown_units_and_invalid_metadata_fail(self):
        for metadata in ({'temperature_unit': 'K'}, {'mass_unit': 'mg'},
                         {'samples': {'missing': {}}},
                         {'samples': {'A_pct': {'independent_repeats': 1.5}}},
                         {'samples': {'A_pct': {'heating_rate_C_min': 0}}}):
            with self.subTest(metadata=metadata), self.assertRaises(ValueError):
                THERMAL.check_data(self.data, metadata)

    def test_unlabelled_mass_units_are_not_guessed(self):
        self.data.write_text('temperature_C,mass\n0,5\n1,4\n', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Mass units must be explicit'):
            THERMAL.check_data(self.data)

    def test_equivalent_numeric_condition_types_compare_equal(self):
        result = THERMAL.check_data(self.data, {'samples': {
            'A_pct': {'heating_rate_C_min': '10'}, 'B_pct': {'heating_rate_C_min': 10}}})
        self.assertNotIn('heating_rate_C_min', result['comparison']['different_conditions'])

    def test_no_replacement_for_proprietary_parser(self):
        with self.assertRaisesRegex(ValueError, 'CSV export'):
            THERMAL.check_data(self.work / 'project.opju')


if __name__ == '__main__':
    unittest.main()
