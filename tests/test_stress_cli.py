import importlib.util
import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_all(*args):
    return subprocess.run([sys.executable, 'scripts/run_all.py', *args], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)


class StressCliTests(unittest.TestCase):
    def test_btc_shock_prints_base_slope_answer_without_writing_files(self):
        results = ROOT / 'results/scenarios.json'
        before = results.stat().st_mtime_ns if results.exists() else None
        done = run_all('--btc-shock', '-40')
        self.assertEqual(done.returncode, 0, done.stderr)
        log_rows = [line.split() for line in done.stdout.splitlines() if line.startswith('log ')]
        self.assertEqual([row[1:5] for row in log_rows],
                         [['0.5', '13.626%', '88.07', '4'], ['1', '15.155%', '79.18', '8'],
                          ['1.5', '16.684%', '71.93', '11']])
        self.assertEqual(log_rows[1][5:], ['1,303', '$m'])
        self.assertEqual(before, results.stat().st_mtime_ns if results.exists() else None)

    def test_spread_shock_adds_to_required_rate(self):
        base = run_all('--btc-shock', '-40')
        wider = run_all('--btc-shock', '-40', '--spread-shock', '200')
        self.assertEqual(wider.returncode, 0, wider.stderr)

        def log_1x(out):
            return float(next(line.split()[2] for line in out.splitlines() if line.startswith('log ')
                              and line.split()[1] == '1').rstrip('%'))
        self.assertAlmostEqual(log_1x(wider.stdout) - log_1x(base.stdout), 2.0, places=3)

    def test_readme_sample_output_is_real(self):
        readme = (ROOT / 'README.md').read_text()
        command = 'python3 scripts/run_all.py --btc-shock -40 --spread-shock 200'
        self.assertIn(command, readme)
        sample = readme.split(command, 1)[1].split('```text\n', 1)[1].split('```', 1)[0]
        done = run_all('--btc-shock', '-40', '--spread-shock', '200')
        self.assertEqual(sample, done.stdout)

    def test_below_coverage_price_is_reported_as_unbounded(self):
        done = run_all('--btc-shock', '-80')
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('unbounded', done.stdout)
        self.assertIn('coverage price', done.stdout)

    def test_invalid_shocks_exit_2_with_reason(self):
        for args, reason in ((['--btc-shock', '-100'], 'between -95 and 400'),
                             (['--btc-shock', 'nan'], 'between -95 and 400'),
                             (['--btc-shock', 'ten'], 'must be a number'),
                             (['--spread-shock', '2500'], 'between -500 and 2000'),
                             (['--spread-shock', 'inf'], 'between -500 and 2000')):
            done = run_all(*args)
            self.assertEqual(done.returncode, 2, args)
            self.assertIn(reason, done.stderr)
            self.assertEqual(done.stdout, '')

    def test_shock_rows_keep_published_minus40_sensitivity(self):
        run = load_script('run_all')
        from strc import credit
        st = run.stress_setup(credit.observations(), credit.coverage_point())
        rows = run.shock_rows(st['models'], st['btc0'], st['sofr0'], st['y0'], st['rate0'], st['notional'], -0.4)
        self.assertEqual([(r['form'], r['assumed_slope_multiplier'], r['required_rate_pct']) for r in rows],
                         [('log', 0.5, 13.626), ('log', 1.0, 15.155), ('log', 1.5, 16.684),
                          ('distance', 0.5, 14.54), ('distance', 1.0, 16.983), ('distance', 1.5, 19.426)])


class ReadmeTableTests(unittest.TestCase):
    def setUp(self):
        self.table = load_script('readme_table')

    def result(self):
        rows = [{'btc_shock_pct': shock, 'form': form, 'assumed_slope_multiplier': m,
                 'required_rate_pct': None if form == 'distance' and shock == -60.0 else 10 + m,
                 'start_price': 80.0, 'months_to_par_band': None if m == 1.5 else 3,
                 'annual_cost_at_required_usd_m': None if form == 'distance' and shock == -60.0 else 900.0}
                for shock in (-20.0, -40.0, -60.0) for form in ('log', 'distance') for m in (0.5, 1.0, 1.5)]
        return {'inputs': {'btc0': 100000.0, 'strc_price0': 99.2, 'rate0_pct': 12, 'notional_usd': 8e9,
                           'sofr0_pct': 3.88, 'as_of': '2026-10-21'}, 'btc_shock_sensitivity': rows}

    def test_block_is_generated_from_result_rows(self):
        block = self.table.render(self.result())
        self.assertIn('needs a 11.000% dividend rate', block)
        self.assertIn('10.500% to 11.500%', block)
        self.assertIn('| -60% | distance | unbounded | unbounded to unbounded | $80.00 | 3 | n/a |', block)
        self.assertEqual(block.count('\n| -'), 6)

    def test_update_replaces_only_marked_block(self):
        text = f'before\n{self.table.START}\nold\n{self.table.END}\nafter\n'
        self.assertEqual(self.table.updated(text, 'NEW'), 'before\nNEW\nafter\n')
        with self.assertRaises(SystemExit):
            self.table.updated('no markers', 'NEW')


if __name__ == '__main__':
    unittest.main()
