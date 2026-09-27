"""Generate manuscript outcome tables and a v6-to-v7 numeric audit from raw CSVs."""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'paper/supplementary'
OUT = ROOT / 'paper/figures'
CONDITIONS = ('C1', 'C1u', 'C1v', 'C2', 'C2f', 'C3', 'C3r', 'C4')
LEASED = frozenset(('C2', 'C2f', 'C3', 'C3r', 'C4'))
REJECTED = ('rejected_fence', 'rejected_remote_epoch', 'rejected_version', 'rejected_duplicate')


def read_csv(path):
    with Path(path).open(newline='') as f:
        return list(csv.DictReader(f))


def cell(rows, series, condition, delay=None):
    return [r for r in rows if r['series'] == series and r['condition'] == condition
            and (delay is None or r.get('delay_s') == str(delay))]


def total(rows, field):
    return sum(int(r.get(field) or 0) for r in rows)


def values(rows, condition):
    ordered = cell(rows, 'ordered_pause', condition)
    duplicate = cell(rows, 'duplicate_pause', condition)
    assert len(ordered) > 0 and (len(duplicate) > 0 or condition == 'C1v')
    return dict(nD=str(len(duplicate)) if duplicate else 'N/A', nO=str(len(ordered)),
                duplicates=f'{total(duplicate, "accepted_duplicates"):,}' if duplicate else 'N/A',
                version=f'{total(ordered, "version_regression"):,}',
                epoch=f'{total(ordered, "epoch_regression"):,}' if condition in LEASED else 'N/A',
                late=f'{total(ordered, "late_accept"):,}' if condition in ('C3', 'C3r') else 'N/A',
                rejected=f'{sum(total(ordered, f) for f in REJECTED):,}')


def replay(rows, condition):
    group = cell(rows, 'lost_ack', condition)
    assert group
    return dict(n=str(len(group)), lost=f'{total(group, "lost_ack"):,}',
                accepted=f'{total(group, "duplicate_accepted"):,}',
                rejected=f'{total(group, "unresolved_ambiguous"):,}',
                stable=f'{total(group, "replay_stable"):,}',
                mismatch=f'{total(group, "replay_mismatch"):,}')


def generate(rows, config):
    for condition in CONDITIONS:
        assert len(cell(rows, 'ordered_pause', condition)) == config['ordered_runs_per_condition']
        if condition != 'C1v':
            assert len(cell(rows, 'duplicate_pause', condition)) == config['duplicate_runs_per_condition']
    for condition in ('C2f', 'C3', 'C4'):
        assert len(cell(rows, 'lost_ack', condition)) == config['replay_runs_per_condition']
    table = [r'\begin{table*}[!t]\caption{Scripted SQLite interleaving outcomes. Counts reflect the specified schedule and sink rules, not failure-rate estimates.}\label{tab:results}',
             r'\centering\footnotesize\setlength{\tabcolsep}{6pt}',
             r'\begin{tabular}{lccccccc}\toprule',
             r'Condition & $n_D$ & $n_O$ & Duplicates & Version reg. & Epoch reg. & Late & Rejected$_O$\\\midrule']
    for condition in CONDITIONS:
        v = values(rows, condition)
        table.append(f"{condition} & {v['nD']} & {v['nO']} & {v['duplicates']} & {v['version']} & {v['epoch']} & {v['late']} & {v['rejected']}" + r'\\')
    table[-1] = table[-1][:-2] + r'\\\bottomrule'
    table += [r'\end{tabular}',
              (r'\par\vspace{4pt}\parbox{.95\textwidth}{\scriptsize $n_D/n_O$: scheduled duplicate/ordered runs; each run has '
               + str(config['keys_per_run'])
               + r" keys. Version and epoch regressions are separate outcomes on the ordered workload. Late means an accepted former-epoch write after grant and before the successor's first remote write. Rejected$_O$: delayed ordered attempts rejected by a guard. N/A: inapplicable or not measured. CPU and provider cost are not measured.}"),
              r'\end{table*}']
    (OUT / 'results_table.tex').write_text('\n'.join(table) + '\n')
    replay_rows = [r'\begin{table}[t]\caption{Scripted lost-ack retries by the current owner. Outcome counts follow the chosen loss draws; zero response mismatches were observed.}\label{tab:replay}',
                   r'\centering\footnotesize\setlength{\tabcolsep}{3.5pt}',
                   r'\begin{tabular}{lrrrr}\toprule',
                   r'Condition & Retry calls & Dup. accepted & Ambig. rejected & Stable replay\\\midrule']
    for condition in ('C2f', 'C3', 'C4'):
        v = replay(rows, condition)
        replay_rows.append(f"{condition} & {v['lost']} & {v['accepted']} & {v['rejected']} & {v['stable']}" + r'\\')
    replay_rows[-1] = replay_rows[-1][:-2] + r'\\\bottomrule'
    replay_rows += [r'\end{tabular}', r'\end{table}']
    (OUT / 'replay_table.tex').write_text('\n'.join(replay_rows) + '\n')
    macros = {
        'ObsOrderedRuns': config['ordered_runs_per_condition'],
        'ObsDuplicateRuns': config['duplicate_runs_per_condition'],
        'ObsReplayRuns': config['replay_runs_per_condition'],
        'ObsAfterRuns': config['after_grant_runs_per_cell'],
        'ObsKeys': config['keys_per_run'],
        'ObsFirstProbabilityPct': round(config['successor_first_probability'] * 100),
        'ObsLostPct': round(config['lost_ack_probability'] * 100),
        'ObsRetryMs': round(config['retry_delay_s'] * 1000),
        'ObsFirstWriteS': config['first_write_delay_s'],
    }
    (OUT / 'study_values.tex').write_text(''.join('\\newcommand{\\' + key + '}{' + str(value) + '}\n'
                                                 for key, value in macros.items()))
    return macros


def audit(old_rows, new_rows, old_config, new_config):
    lines = ['# v7 result-number audit', '',
             'The before values come from the publicly published v6 commit; the after values come from regenerated `sqlite_trials.csv`. Every table cell below was counted from those CSVs. N/A means the metric was not applicable. The schedules differ, so a change is a correction to the model, not a performance improvement.', '',
             '## Table VI', '',
             '| Condition | Metric | Before | After |', '| --- | --- | ---: | ---: |']
    fields = ('nD', 'nO', 'duplicates', 'version', 'epoch', 'late', 'rejected')
    for condition in CONDITIONS:
        before, after = values(old_rows, condition), values(new_rows, condition)
        for field in fields:
            lines.append(f'| {condition} | {field} | {before[field]} | {after[field]} |')
    lines += ['', '## Table VII', '', '| Condition | Metric | Before | After |', '| --- | --- | ---: | ---: |']
    for condition in ('C2f', 'C3', 'C4'):
        before, after = replay(old_rows, condition), replay(new_rows, condition)
        for field in ('n', 'lost', 'accepted', 'rejected', 'stable', 'mismatch'):
            lines.append(f'| {condition} | {field} | {before[field]} | {after[field]} |')
    old_abstract = total(cell(old_rows, 'ordered_pause', 'C3r'), 'late_accept')
    new_abstract = total(cell(new_rows, 'ordered_pause', 'C3r'), 'late_accept')
    lines += ['', '## Abstract and table-caption context', '',
              '| Item | Before | After |', '| --- | ---: | ---: |',
              f'| Abstract remote late-accept count | {old_abstract} | Omitted; qualitative mechanism claim (new raw count: {new_abstract}) |',
              f"| Table VI duplicate runs per condition | {old_config['duplicate_runs_per_condition']} | {new_config['duplicate_runs_per_condition']} |",
              f"| Table VI ordered runs per condition | {old_config['ordered_runs_per_condition']} | {new_config['ordered_runs_per_condition']} |",
              f"| Table VI keys per run | {old_config['keys_per_run']} | {new_config['keys_per_run']} |",
              f"| Table VI caption, invalid trials | 0 by construction | Removed: no fault verification occurs |",
              f"| Table VI caption, at-risk submissions per duplicate cell | {old_config['duplicate_runs_per_condition'] * old_config['keys_per_run']:,} | {new_config['duplicate_runs_per_condition'] * new_config['keys_per_run']:,} |",
              f"| Table VI caption, at-risk submissions per ordered cell | {old_config['ordered_runs_per_condition'] * old_config['keys_per_run']:,} | {new_config['ordered_runs_per_condition'] * new_config['keys_per_run']:,} |",
              f"| Table VII replay runs per condition | {old_config['replay_runs_per_condition']} | {new_config['replay_runs_per_condition']} |",
              f"| Table VII configured loss probability | {old_config['lost_ack_probability']} | {new_config['lost_ack_probability']} |",
              f"| Table VII caption, invalid trials | 0 by construction | Removed: no fault verification occurs |",
              f"| Table VII response mismatches | 0 | 0 |",
              f"| Abstract illustrative capacity, peak requests/s | 600 | 600 |",
              f"| Abstract illustrative capacity, safe requests/s per replica | 120 | 120 |",
              f"| Abstract illustrative capacity, reserve | 20% | 20% |",
              f"| Abstract illustrative capacity, required replicas | 7 | 7 |",
              f"| Abstract exploratory schedules per cell | 30 | Omitted (mixed scheduled-run counts) |",
              '', 'The old abstract also reported zero version regressions for C1v and zero epoch regressions for co-located fences; those observations remain zero under the corrected schedule. The old abstract reported the 7-replica capacity illustration from declared 600 requests/s, 120 requests/s per replica and 20% reserve; that calculation is unchanged by the exploratory-study correction.', '']
    (ROOT / 'docs/V7_NUMBER_AUDIT.md').write_text('\n'.join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--old-ref', default=None, help='Git commit containing the previous public raw CSV')
    args = parser.parse_args()
    rows = read_csv(DATA / 'sqlite_trials.csv')
    config = json.loads((DATA / 'experiment_config.json').read_text())
    generate(rows, config)
    if args.old_ref:
        old_text = subprocess.check_output(['git', 'show', f'{args.old_ref}:paper/supplementary/sqlite_trials.csv'], cwd=ROOT, text=True)
        old_rows = list(csv.DictReader(StringIO(old_text)))
        old_config = {'duplicate_runs_per_condition': len(cell(old_rows, 'duplicate_pause', 'C1')),
                      'ordered_runs_per_condition': len(cell(old_rows, 'ordered_pause', 'C1')),
                      'keys_per_run': int(cell(old_rows, 'ordered_pause', 'C1')[0]['items']),
                      'replay_runs_per_condition': len(cell(old_rows, 'lost_ack', 'C2f')),
                      'lost_ack_probability': .05}
        audit(old_rows, rows, old_config, config)
    print('Generated observed tables and study values from raw CSVs.')


if __name__ == '__main__':
    main()
