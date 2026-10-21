from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts/library.py'
spec = importlib.util.spec_from_file_location('tested_library', SCRIPT)
lib = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lib
spec.loader.exec_module(lib)


class LibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = lib.load_records()
        cls.recipes = json.loads((ROOT / 'references/pattern-checks.json').read_text(encoding='utf-8'))

    def test_original_ids_remain_addressable(self):
        found = {record.identifier for record in self.records}
        before = {'TXT':42, 'LAY':19, 'TYP':14, 'COL':13, 'CTL':18, 'MOT':15, 'IMG':11, 'PAG':12, 'PRC':16}
        self.assertEqual(sum(before.values()), 160)
        for prefix, count in before.items():
            self.assertTrue({f'{prefix}-{i:02d}' for i in range(1, count+1)} <= found)

    def test_recipes_cover_all_actual_antipatterns_and_boundaries(self):
        self.assertEqual(lib.validate_pattern_checks(self.recipes, self.records), [])
        self.assertEqual(len(self.recipes['patterns']), sum(record.kind == 'antipattern' for record in self.records))

    def test_missing_recipe_is_not_silently_accepted(self):
        recipes = deepcopy(self.recipes); removed = recipes['patterns'].pop()['id']
        self.assertTrue(any(removed in item for item in lib.validate_pattern_checks(recipes, self.records)))

    def test_duplicate_and_foreign_canonical_are_errors(self):
        recipes = deepcopy(self.recipes)
        recipes['patterns'].append(deepcopy(recipes['patterns'][0]))
        recipes['patterns'][1]['canonical']['path'] = '../../outside.md'
        findings = lib.validate_pattern_checks(recipes, self.records)
        self.assertTrue(any('duplicate' in item for item in findings))
        self.assertTrue(any('path mismatch' in item for item in findings))

    def test_grounding_needs_explicit_limits(self):
        recipes = deepcopy(self.recipes); recipes['patterns'][0]['grounding'][0]['limits'] = ''
        self.assertTrue(any('limits' in item for item in lib.validate_pattern_checks(recipes, self.records)))

    def test_all_stage_pages_are_lossless_and_bounded(self):
        lookup = {record.identifier: record for record in self.records}
        for stage, keys in lib.START_STAGES.items():
            payload = lib.render_start_guidance(stage) + '\n' + '\n'.join(lookup[key].render() for key in keys)
            for limit in (1600, 6000, 8000):
                pages = lib.paginate(payload, limit)
                self.assertEqual(''.join(pages), payload)
                for page in range(1,len(pages)+1):
                    self.assertLessEqual(len(lib.render_page(payload,page,limit,f'start --stage {stage}')),limit)

    def test_targeted_check_output_and_platform_continuation(self):
        result = subprocess.run([sys.executable,'-X','utf8',str(SCRIPT),'checks','CTL-18','MOT-15','--limit','1600'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('CTL-18',result.stdout); self.assertLessEqual(len(result.stdout),1600)
        platform = subprocess.run([sys.executable,'-X','utf8',str(SCRIPT),'start','--stage','content','--platform','mobile','--limit','1600'],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(platform.returncode,0,platform.stderr)
        self.assertIn('--platform mobile',platform.stdout)

    def test_unknown_id_and_reference_escape_fail(self):
        for args in (['checks','TXT-99'],['read','../SKILL.md'],['show','TXT-01','--page','0']):
            result = subprocess.run([sys.executable,str(SCRIPT),*args],capture_output=True)
            self.assertEqual(result.returncode,2)

    def test_selecting_every_recipe_stays_paged(self):
        recipes = lib.read_pattern_checks(self.records)
        ids = list(recipes)
        payload = lib.render_pattern_checks(ids,recipes)
        for limit in (1600,6000,8000):
            pages = lib.paginate(payload,limit)
            self.assertEqual(''.join(pages),payload)
            self.assertLessEqual(len(lib.render_page(payload,1,limit,'checks '+' '.join(ids))),limit)


if __name__ == '__main__':
    unittest.main()
