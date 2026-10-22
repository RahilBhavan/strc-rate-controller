"""Observable ledger invariants on the frozen decisions; no invented observations."""
import math
import pathlib
import subprocess
import sys
import unittest
from dataclasses import replace
from unittest.mock import patch

from strc import evaluation, fit
from strc.features import decisions


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = decisions()
        cls.report = evaluation.chronological_report(cls.rows)

    def test_same_dates_strict_cutoffs_and_reconstructible_metrics(self):
        self.assertEqual(self.report['n_decisions'], 14)
        self.assertEqual(self.report['n_holdout'], 3)
        self.assertEqual([s['initial_training_n'] for s in self.report['splits']], [11, 6, 8, 10])
        for split in self.report['splits']:
            start = split['initial_training_n']
            for policy in split['policies']:
                ledger, summary = policy['ledger'], policy['summary']
                self.assertEqual(len(split['policies']), 10)
                self.assertEqual([r['notice_date'] for r in ledger],
                                 [r.notice.isoformat() for r in self.rows[start:]])
                errors, deltas = [], []
                for i, entry in enumerate(ledger, start):
                    target = self.rows[i]
                    self.assertLess(entry['fit_through'], entry['notice_date'])
                    self.assertLess(entry['history_through'], entry['notice_date'])
                    self.assertEqual(entry['fit_n'], start if split['name'] == 'fixed_holdout' else i)
                    self.assertEqual(entry['history_n'], i)
                    self.assertEqual(entry['source_url'], target.source_url)
                    error = abs(fit.snap(entry['raw_pred_bp']) - target.change_bp)
                    errors.append(error)
                    deltas.append(error - abs(target.change_bp))
                self.assertEqual(summary['mae_bp'], sum(errors) / len(errors))
                self.assertEqual(summary['wins_vs_hold'], sum(d < 0 for d in deltas))
                self.assertEqual(summary['ties_vs_hold'], sum(d == 0 for d in deltas))
                self.assertEqual(summary['losses_vs_hold'], sum(d > 0 for d in deltas))
                self.assertEqual(summary['losing_notice_dates'], [r['notice_date'] for r, d
                                                                in zip(ledger, deltas) if d > 0])
                omitted = [(sum(errors) - e) / (len(errors) - 1) for e in errors]
                self.assertEqual(summary['omit_one_date_mae_range_bp'], [min(omitted), max(omitted)])
                raw_error = sum(abs(r['raw_pred_bp'] - r['actual_bp']) for r in ledger) / len(ledger)
                self.assertEqual(summary['raw_mae_bp'], raw_error)

    def test_matches_existing_policy_predictions(self):
        legacy = fit.evaluate(self.rows)
        fixed, replay = self.report['splits'][:2]
        for old, new, expanding in zip(legacy, fixed['policies'], replay['policies']):
            self.assertEqual(old['post_break']['pred_bp'], [r['pred_bp'] for r in new['ledger']])
            self.assertEqual(old['expanding_replay']['pred_bp'], [r['pred_bp'] for r in expanding['ledger']])

    def test_baselines_and_actual_losing_cases(self):
        fixed = {p['policy']: p for p in self.report['splits'][0]['policies']}
        self.assertEqual(fixed['hold']['summary']['mae_bp'], 0)
        self.assertEqual([r['actual_bp'] for r in fixed['hold']['ledger']], [0, 0, 0])
        self.assertAlmostEqual(fixed['framework']['summary']['mae_bp'], 100 / 3)
        self.assertEqual(fixed['framework']['summary']['losses_vs_hold'], 3)
        for split in self.report['splits']:
            prior, med = split['policies'][-2:]
            start = split['initial_training_n']
            self.assertEqual([r['raw_pred_bp'] for r in prior['ledger']],
                             [r.change_bp for r in self.rows[start - 1:-1]])
            if split['name'] == 'fixed_holdout':
                self.assertEqual(len({r['raw_pred_bp'] for r in med['ledger']}), 1)
        self.assertIn('Hindsight', fixed['proportional+mNAV']['feature_status'])

    def test_current_and_future_outcomes_cannot_change_prediction(self):
        # Poison target and later outcomes at a replay point, including the rate
        # field from which a careless predictor could recover the target change.
        i = 8
        poisoned = [replace(r, change_bp=900, rate=99) if j >= i else r
                    for j, r in enumerate(self.rows)]
        after = evaluation.chronological_report(poisoned)
        before_replay = self.report['splits'][1]['policies']
        after_replay = after['splits'][1]['policies']
        for before, changed in zip(before_replay, after_replay):
            for a, b in zip(before['ledger'][:3], changed['ledger'][:3]):
                self.assertEqual(a['params'], b['params'])
                self.assertEqual(a['raw_pred_bp'], b['raw_pred_bp'])

    def test_fixed_holdout_fitting_ignores_holdout_outcomes(self):
        poisoned = [replace(r, change_bp=900) if r.notice >= fit.BREAK else r for r in self.rows]
        after = evaluation.chronological_report(poisoned)
        for before, changed in zip(self.report['splits'][0]['policies'], after['splits'][0]['policies']):
            self.assertEqual([r['params'] for r in before['ledger']],
                             [r['params'] for r in changed['ledger']])
        # Prior-change uses earlier holdout outcomes only after they are observed.
        prior = after['splits'][0]['policies'][-2]['ledger']
        self.assertEqual([r['raw_pred_bp'] for r in prior[1:]], [900, 900])

    def test_outcome_fields_are_masked_at_prediction_boundary(self):
        spy = fit.Rule('spy', 0, lambda rows: None,
                       lambda p, r, h: r.change_bp + (r.rate - r.prev_rate) * 100, 'test only')
        with patch.object(evaluation, 'RULES', [spy]):
            report = evaluation.chronological_report(self.rows)
        self.assertTrue(all(r['raw_pred_bp'] == 0 for s in report['splits']
                            for r in s['policies'][0]['ledger']))

    def test_invalid_decision_tables_fail_explicitly(self):
        invalid = [[], self.rows[:6], list(reversed(self.rows)),
                   [self.rows[0], *self.rows],
                   [replace(self.rows[0], change_bp=math.nan), *self.rows[1:]],
                   [replace(self.rows[0], regime='daily_proposed'), *self.rows[1:]]]
        for rows in invalid:
            with self.subTest(n=len(rows)), self.assertRaises(ValueError):
                evaluation.chronological_report(rows)

    def test_cli_reports_losses_and_rejects_unknown_split(self):
        root = pathlib.Path(__file__).resolve().parents[1]
        command = [sys.executable, 'scripts/evaluate_policies.py']
        good = subprocess.run([*command, '--policy', 'framework'], cwd=root,
                              capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)
        self.assertIn('MAE=33.33 bp', good.stdout)
        self.assertIn('wins/ties/losses vs hold=0/0/3', good.stdout)
        self.assertIn('2026-07-31: actual=0', good.stdout)
        self.assertIn('no predictive edge', good.stdout)
        bad = subprocess.run([*command, '--split', 'unknown'], cwd=root,
                             capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)
        self.assertIn('invalid choice', bad.stderr)
