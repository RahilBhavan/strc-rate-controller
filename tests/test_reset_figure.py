import csv
import importlib.util
import pathlib
import re
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from strc.history import load  # noqa: E402

spec = importlib.util.spec_from_file_location('reset_figure', ROOT / 'scripts' / 'reset_figure.py')
reset_figure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reset_figure)


def readme_rows():
    block = (ROOT / 'docs' / 'reset-history.md').read_text().split(reset_figure.START, 1)[1].split(reset_figure.END, 1)[0]
    return [line.split(' | ') for line in block.splitlines() if re.match(r'\| \d{4}-\d{2}-\d{2} ', line)]


class ResetFigureTests(unittest.TestCase):
    def test_committed_figure_and_table_match_the_filings(self):
        done = subprocess.run([sys.executable, 'scripts/reset_figure.py', '--check'], cwd=ROOT,
                              capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_every_table_row_is_a_filed_rate_linked_to_its_cached_filing(self):
        cached = set()
        for path in sorted((ROOT / 'provenance').glob('sources-*.csv')):
            with path.open() as f:
                cached |= {row['url'] for row in csv.DictReader(f)}
        rows = readme_rows()
        filed = load()
        self.assertEqual(len(rows), len(filed))
        for row, ann in zip(rows, filed):
            self.assertEqual(row[0], f'| {ann.notice}')
            self.assertEqual(row[2], f'{ann.rate:.2f}%')
            url = re.search(r'\((https://www\.sec\.gov/[^)]+)\)', row[-1]).group(1)
            self.assertEqual(url, ann.source_url)
            self.assertIn(url, cached)

    def test_hold_annotations_refuse_data_they_no_longer_describe(self):
        rows = reset_figure.resets()
        for row in rows:
            if row['kind'] == 'hold':
                row['vwap'] = 99.5
        with self.assertRaises(SystemExit):
            reset_figure.svg(rows, reset_figure.closes(), reset_figure.objective_url())


if __name__ == '__main__':
    unittest.main()
