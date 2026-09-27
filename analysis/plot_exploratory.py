"""Plot controlled after-grant acceptance from the raw SQLite trial CSV."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--source', choices=('sqlite', 'pg'), default='sqlite')
args = parser.parse_args()
rows = list(csv.DictReader((ROOT / 'paper/supplementary' / ('pg_trials.csv' if args.source == 'pg' else 'sqlite_trials.csv')).open()))
config = json.loads((ROOT / 'paper/supplementary/experiment_config.json').read_text())
plt.rcParams.update({'font.family': 'serif', 'font.serif': ['DejaVu Serif']})
fig, ax = plt.subplots(figsize=(4.7, 2.7))
for condition, marker in (('C3', 's'), ('C3r', 'o')):
    points = []
    for delay in config['resume_delays_s']:
        cell = [r for r in rows if r['series'] == 'after_grant'
                and r['condition'] == condition and int(r['delay_s']) == delay]
        assert len(cell) == config['after_grant_runs_per_cell']
        points.append(sum(int(r.get('late_accept') or 0) for r in cell)
                      / sum(int(r['at_risk_attempts']) for r in cell))
    ax.plot(config['resume_delays_s'], points, linestyle='None', marker=marker,
            markersize=7, label=condition)
ax.set(title=('PostgreSQL 16 scheduled SQL' if args.source == 'pg' else 'SQLite rule model'), xlabel='Former worker resume delay after grant (s)',
       ylabel='Late accepts / at-risk attempts', xticks=config['resume_delays_s'],
       ylim=(-.02, 1.05), yticks=[0, .25, .5, .75, 1])
ax.axvline(config['first_write_delay_s'], color='#666666', linestyle=':',
           label='Successor first write')
ax.grid(axis='y', alpha=.2)
ax.legend(fontsize=7, frameon=False)
fig.tight_layout()
fig.savefig(ROOT / 'paper/figures/after_grant.pdf')
