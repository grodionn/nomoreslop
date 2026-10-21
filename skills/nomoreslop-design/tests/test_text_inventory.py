import importlib.util
import argparse
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/audit_project.py'
spec = importlib.util.spec_from_file_location('audit_project', SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class InventoryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / 'index.html').write_text('''<h1>Название</h1><p>Архитектура, которая<br>становится частью вас</p>
<img alt="План этажа"><button aria-label="Следующая работа">→</button>
<div hidden>Скрытая панель</div><div aria-hidden="true">Видимая декорация</div>
<!-- Не посетительский комментарий --><script>const message="Спасибо за заявку";</script>
<style>.a::after {content: "В наличии"}</style>''', encoding='utf-8')
        (self.root / 'drawing.svg').write_text('<svg><text><tspan>Одна заявка.</tspan><tspan> Одна система.</tspan></text></svg>', encoding='utf-8')
        (self.root / 'component.js').write_text('''// "Комментарий не текст"
const markup=`<p>Пример ${data.name} <b>сообщения</b></p>`;
const states=['Новые', 'В работе'];
const nested=`<section>${states.map(x=>`<span>${x}</span>`).join('')}</section>`;
const escaped='Ошибка\\u0020сети';
/* <h2>Псевдотекст комментария</h2> */''', encoding='utf-8')
        (self.root / 'App.tsx').write_text('const Demo=()=> <div><h2>Доступные тарифы</h2><span>{name}</span><input placeholder="Имя"/></div>;', encoding='utf-8')
        (self.root / 'style.css').write_text('/* content: "Комментарий CSS" */ .x::after{content:"Новое"} .n{content:attr(data-label)}', encoding='utf-8')
        (self.root / 'node_modules').mkdir()
        (self.root / 'node_modules' / 'vendor.js').write_text('const a="Сторонний мусор"', encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def collect(self, *args):
        result = subprocess.run([sys.executable, '-X', 'utf8', str(SCRIPT), 'collect-text', str(self.root), *args], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_markup_svg_js_and_css_coverage(self):
        data = self.collect()
        texts = {item['text'] for item in data['entries']}
        self.assertIn('Архитектура, которая становится частью вас', texts)
        self.assertIn('Одна заявка. Одна система.', texts)
        self.assertIn('Ошибка сети', texts)
        self.assertIn('Доступные тарифы', texts)
        self.assertIn('Новое', texts)
        self.assertIn('В наличии', texts)
        self.assertIn('Спасибо за заявку', texts)
        self.assertNotIn('Не посетительский комментарий', texts)
        self.assertNotIn('Комментарий не текст', texts)
        self.assertNotIn('Комментарий CSS', texts)
        self.assertNotIn('Сторонний мусор', texts)
        self.assertNotIn('Псевдотекст комментария', texts)
        hidden = next(item for item in data['entries'] if item['text'] == 'Скрытая панель')
        self.assertEqual(hidden['visibility'], 'declared-hidden')
        decoration = next(item for item in data['entries'] if item['text'] == 'Видимая декорация')
        self.assertEqual(decoration['visibility'], 'unverified')
        self.assertTrue(any(item['dynamic'] for item in data['entries']))
        self.assertTrue(any('CSS content' in item['reason'] for item in data['gaps']))
        self.assertTrue(any('not an AST' in item['reason'] for item in data['gaps']))

    def test_rendered_state_and_canonical_reconciliation(self):
        canonical = self.root / 'content.md'
        canonical.write_text('Название\nОшибка сети\nСледующая работа', encoding='utf-8')
        snap = self.root / 'snapshot.json'
        snap.write_text(json.dumps({'state': 'После отправки', 'version': 'abc123', 'viewport': {'width': 390, 'height': 844}, 'captured_at': '2026-10-20T10:00:00Z', 'entries': [{'text': 'Заявка принята', 'selector': '#status', 'visibility': 'visible'}]}, ensure_ascii=False), encoding='utf-8')
        data = self.collect('--canonical', str(canonical), '--rendered', str(snap))
        self.assertTrue(next(item for item in data['entries'] if item['text'] == 'Название')['canonical_match'])
        observed = next(item for item in data['entries'] if item['text'] == 'Заявка принята')
        self.assertEqual(observed['state'], 'После отправки')
        self.assertEqual(observed['origin'], 'rendered-snapshot')
        self.assertFalse(observed['canonical_match'])

    def test_read_only_and_explicit_filters(self):
        before = {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        data = self.collect('--include', '*.svg')
        self.assertEqual(data['summary']['files'], 1)
        self.assertEqual(before, {str(p): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        protected = self.root / 'index.html'
        result = subprocess.run([sys.executable, str(SCRIPT), 'collect-text', str(self.root), '--output', str(protected)], capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(protected.read_bytes(), before[str(protected)])

    def test_invalid_snapshot_fails_explicitly(self):
        invalid = self.root / 'snapshot.json'
        invalid.write_text('{"entries": []}', encoding='utf-8')
        result = subprocess.run([sys.executable, str(SCRIPT), 'collect-text', str(self.root), '--rendered', str(invalid)], capture_output=True)
        self.assertEqual(result.returncode, 2)

    def test_unterminated_template_and_large_file_have_explicit_gaps(self):
        (self.root / 'broken.js').write_text('const a=`Незавершённый ${name}', encoding='utf-8')
        data = self.collect()
        unfinished = next(item for item in data['entries'] if item['origin'] == 'unterminated-string')
        self.assertTrue(unfinished['dynamic'])
        limited = self.collect('--max-file-bytes', '1')
        self.assertEqual(limited['summary']['candidates'], 0)
        self.assertTrue(any('exceeds max-file-bytes' in item['reason'] for item in limited['gaps']))

    def test_directory_pruning_happens_before_descent(self):
        (self.root / '.git').mkdir()
        (self.root / '.git' / 'ignored.js').write_text('"ignored"')
        visited = []
        real_walk = module.os.walk

        def observed_walk(*args, **kwargs):
            for directory, dirs, names in real_walk(*args, **kwargs):
                visited.append(Path(directory).name)
                yield directory, dirs, names

        inventory = module.Inventory()
        with mock.patch.object(module.os, 'walk', observed_walk):
            list(module.project_files(self.root, inventory))
        self.assertNotIn('node_modules', visited)
        self.assertNotIn('.git', visited)

    def test_file_stat_error_is_reported_and_each_source_is_read_once(self):
        actual_stat, actual_read = Path.stat, Path.read_bytes
        reads = {}

        def flaky_stat(path, *args, **kwargs):
            if path.name == 'drawing.svg':
                raise PermissionError('fixture stat denied')
            return actual_stat(path, *args, **kwargs)

        def counted_read(path):
            reads[path] = reads.get(path, 0) + 1
            return actual_read(path)

        args = argparse.Namespace(root=self.root, include=[], exclude=[], max_file_bytes=2_000_000, rendered=[], canonical=None, output=None)
        output = io.StringIO()
        with mock.patch.object(Path, 'stat', flaky_stat), mock.patch.object(Path, 'read_bytes', counted_read), contextlib.redirect_stdout(output):
            module.collect(args)
        data = json.loads(output.getvalue())
        self.assertTrue(any(item['source'] == 'drawing.svg' and 'fixture stat denied' in item['reason'] for item in data['gaps']))
        self.assertTrue(reads)
        self.assertTrue(all(count == 1 for count in reads.values()))


if __name__ == '__main__':
    unittest.main(verbosity=2)
