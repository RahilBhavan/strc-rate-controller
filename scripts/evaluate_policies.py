"""Print the chronological report from frozen inputs (no network)."""
import argparse
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from strc.evaluation import BASELINES, chronological_report  # noqa: E402
from strc.features import decisions  # noqa: E402
from strc.fit import RULES  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=['fixed_holdout', 'expanding_6', 'expanding_8', 'expanding_10'],
                        default='fixed_holdout')
    parser.add_argument('--policy', choices=[r.name for r in [*RULES, *BASELINES]],
                        help='Show one policy with its full dated ledger.')
    args = parser.parse_args()
    report = chronological_report(decisions())
    print(report['interpretation'])
    print(f"{report['n_decisions']} dated decisions; {report['n_holdout']} holdout observations. "
          'mNAV hindsight-scaled; notice-close availability unverified.')
    split = next(s for s in report['splits'] if s['name'] == args.split)
    print(f"{split['name']}: initial training n={split['initial_training_n']}")
    for policy in split['policies']:
        if args.policy and policy['policy'] != args.policy:
            continue
        s = policy['summary']
        print(f"{policy['policy']}: n={s['n']}, MAE={s['mae_bp']:.2f} bp, "
              f"raw MAE={s['raw_mae_bp']:.2f} bp, "
              f"wins/ties/losses vs hold={s['wins_vs_hold']}/{s['ties_vs_hold']}/{s['losses_vs_hold']}")
        print('  Losing dates: ' + (', '.join(s['losing_notice_dates']) or 'none'))
        print(f"  Omit-one-date MAE range (no refit, not CI): {s['omit_one_date_mae_range_bp']} bp")
        if args.policy:
            print('  ' + policy['feature_status'])
            for row in policy['ledger']:
                print(f"  {row['notice_date']}: actual={row['actual_bp']:g}, "
                      f"raw={row['raw_pred_bp']:.4f}, snapped={row['pred_bp']:g}, "
                      f"error={row['absolute_error_bp']:g} bp; "
                      f"fit n={row['fit_n']} through {row['fit_through']}; "
                      f"history n={row['history_n']} through {row['history_through']}")
                print('    ' + row['source_url'])


if __name__ == '__main__':
    main()
