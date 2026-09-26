"""Plot controlled after-grant acceptance from the raw SQLite trial CSV."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
rows = list(csv.DictReader((ROOT / 'paper/supplementary/sqlite_trials.csv').open()))
fig, ax = plt.subplots(figsize=(4.7, 2.7))
for condition, marker in (('C3', 's'), ('C3r', 'o')):
    points = []
    for delay in (0, 1, 5):
        cell = [r for r in rows if r['series'] == 'after_grant'
                and r['condition'] == condition and int(r['delay_s']) == delay]
        assert len(cell) == 30
        points.append(sum(int(r.get('late_accept') or 0) for r in cell)
                      / sum(int(r['at_risk_attempts']) for r in cell))
    ax.plot((0, 1, 5), points, marker=marker, label=condition, linewidth=1.5)
ax.set(xlabel='Former worker resume delay after grant (s)',
       ylabel='Late accepts / at-risk attempts', xticks=[0, 1, 5],
       ylim=(-.05, 1.1))
ax.axvline(2, color='#666666', linestyle=':', label='Successor first write (2 s)')
ax.grid(axis='y', alpha=.2)
ax.legend(fontsize=7, frameon=False)
fig.tight_layout()
fig.savefig(ROOT / 'paper/figures/after_grant.pdf')
