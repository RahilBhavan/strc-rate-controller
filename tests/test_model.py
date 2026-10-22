import datetime as dt
import math
import unittest
from dataclasses import replace

from strc import credit, fit, history, rules, sim
from strc.data import Bar, vwap
from strc.features import decisions, window_bars

D = dt.date.fromisoformat


class ModelTests(unittest.TestCase):
    def test_source_history(self):
        rows = history.load()  # regex extraction from every frozen filing
        self.assertEqual(len(rows), 17)
        self.assertEqual(rows[0].rate, 9)
        self.assertEqual(rows[-2].rate, 12)
        self.assertTrue(all(a.quote and a.source_url.startswith('https://www.sec.gov/') for a in rows))

    def test_contingent_excluded(self):
        rows = decisions()
        self.assertEqual(len(rows), 14)
        self.assertFalse(any(r.regime == 'daily_proposed' for r in rows))
        self.assertEqual(sum(r.notice >= fit.BREAK for r in rows), 3)

    def test_no_unannounced_extrapolation(self):
        with self.assertRaises(ValueError):
            history.rate_on(D('2026-12-01'))

    def test_current_unconditional_rate(self):
        self.assertEqual(history.rate_on(D('2026-10-21')), 12)

    def test_reduction_cap(self):
        for proposed in (0, 5, 11):
            self.assertEqual(rules.clamp(proposed, 12, 0, 4).rate, 11.75)
        self.assertEqual(rules.clamp(10, 12, .5, 4).rate, 11.25)

    def test_sofr_floor(self):
        self.assertEqual(rules.clamp(0, 5, 1, 4.8).rate, 4.8)

    def test_arrears_block_reduction(self):
        self.assertEqual(rules.clamp(11, 12, 0, 4, False).rate, 12)
        self.assertEqual(rules.clamp(20, 12, 0, 4, False).rate, 20)

    def test_framework_is_not_a_cap_on_increases(self):
        self.assertEqual(rules.clamp(100, 12, 0, 4).rate, 100)

    def test_proxy_window_no_future_bars(self):
        bars = [Bar(dt.date(2026, 1, d), 100, 100, 100, 100, 1) for d in range(1, 31)]
        w = window_bars(bars, D('2026-01-20'), '5d')
        self.assertTrue(all(b.date <= D('2026-01-20') for b in w))
        self.assertEqual(len(w), 5)

    def test_calendar_month_not_rolling_30(self):
        bars = [Bar(dt.date(2026, 3, d), 100, 100, 100, 100, 1) for d in range(1, 32)]
        self.assertEqual(len(window_bars(bars, D('2026-03-31'), 'month')), 31)

    def test_empty_vwap_rejected(self):
        with self.assertRaises(ValueError):
            vwap([])

    def test_fit_and_replay(self):
        out = fit.evaluate(decisions())
        self.assertEqual(len(out), 8)
        for row in out:
            self.assertEqual(row['post_break']['n'], 3)
            self.assertEqual(row['expanding_replay']['n'], 8)
            self.assertTrue(math.isfinite(row['post_break']['mae_bp']))

    def test_holdout_does_not_change_fitted_params(self):
        rows = decisions()
        perturbed = [replace(r, change_bp=900) if r.notice >= fit.BREAK else r for r in rows]
        self.assertEqual([r['params'] for r in fit.evaluate(rows)],
                         [r['params'] for r in fit.evaluate(perturbed)])

    def test_stress_and_sensitivity(self):
        # Assumed response, deliberately independent of fitted coefficients.
        m = credit.SpreadModel('distance', 4, 2, 20000)
        a = sim.anchor(m, 100000, 4, 12)
        b = sim.anchor(replace(m, b=4), 100000, 4, 12)
        p = sim.run(sim.Scenario('btc -40', btc_shock=-.4), a, 100000, 4, 12)
        q = sim.run(sim.Scenario('btc -40 higher slope', btc_shock=-.4), b, 100000, 4, 12)
        self.assertLess(q.price[0], p.price[0])
        self.assertEqual(len(p.rate), 25)
        self.assertTrue(all(x >= 0 for x in p.rate))

    def test_invalid_scenarios(self):
        m = credit.SpreadModel('log', 8, -1, 20000)
        for sc in (sim.Scenario('bad', btc_shock=-1), sim.Scenario('bad', months=0),
                   sim.Scenario('bad', btc_shock=math.nan), sim.Scenario('bad', sofr_path=[])):
            with self.subTest(sc=sc), self.assertRaises(ValueError):
                sim.run(sc, m, 100000, 4, 12)

    def test_proxy_coverage_source(self):
        cp = credit.coverage_point()
        self.assertGreater(cp['holdings_btc'], 0)
        self.assertGreater(cp['b_star'], 0)
        self.assertEqual(len(credit.observations()), 309)

    def test_regime_window(self):
        self.assertEqual(rules.sofr_window('semi_monthly', D('2026-10-16')),
                         (D('2026-09-01'), D('2026-09-30')))
        with self.assertRaises(ValueError):
            rules.sofr_window('semi_monthly', D('2026-10-01'))

    def test_short_sofr_path_extends_last_value(self):
        model = credit.SpreadModel('log', 8, 0, 20000)
        short = sim.run(sim.Scenario('short', sofr_path=[4]), model, 100000, 4, 12)
        full = sim.run(sim.Scenario('full', sofr_path=[4] * 25), model, 100000, 4, 12)
        self.assertEqual(short.rate, full.rate)
        self.assertEqual(short.price, full.price)

    def test_excess_dividends_count_intervals_not_terminal_point(self):
        model = credit.SpreadModel('log', 7.9, 0, 20000)
        path = sim.run(sim.Scenario('overpay', policy='hold_12'), model, 100000, 4, 12)
        # 10 bp on $1.2bn for two years = $2.4m, not 25 monthly charges.
        self.assertEqual(path.row(1200000000)['excess_dividends_usd_m'], 2.4)

    def test_evaluation_errors_and_replay_sensitivity_are_traceable(self):
        for result in fit.evaluate(decisions()):
            metrics = result['post_break']
            self.assertEqual(len(metrics['notice_dates']), 3)
            errors = [abs(a - p) for a, p in zip(metrics['actual_bp'], metrics['pred_bp'])]
            self.assertEqual(metrics['absolute_error_bp'], errors)
            self.assertAlmostEqual(metrics['mae_bp'], sum(errors) / 3)
            self.assertEqual([r['n'] for r in result['replay_start_sensitivity']], [8, 6, 4])
            if result['rule'] == 'proportional+mNAV':
                self.assertIn('hindsight', result['feature_status'])

    def test_elected_increase_respects_sofr_floor_but_carry_does_not(self):
        self.assertEqual(rules.clamp(4, 3, 0, 5).rate, 5)
        self.assertEqual(rules.clamp(3, 3, 0, 5).rate, 3)
        self.assertEqual(rules.clamp(4, 3, 0, 5, False).rate, 5)

    def test_custom_horizon_labels_match_elapsed_months(self):
        path = sim.run(sim.Scenario('one', months=1), credit.SpreadModel('log', 8, 0, 20000),
                       100000, 4, 12)
        row = path.row(1200000000)
        self.assertEqual(row['horizon_months'], 1)
        self.assertIn('rate_after_1m_pct', row)
        self.assertNotIn('rate_after_24m_pct', row)
