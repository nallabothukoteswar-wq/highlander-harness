# PostgreSQL result audit

All values in this table were counted from `paper/supplementary/pg_trials.csv`, downloaded from the [PostgreSQL CI run](https://github.com/nallabothukoteswar-wq/highlander-harness/actions/runs/36291161498). The SQL runner created 343 trial rows and 43 summary rows on PostgreSQL 16.15 (Debian 16.15-1.pgdg13+2).

| Manuscript result | Measured count |
| --- | ---: |
| C1 version regressions | 2,071 |
| C2 epoch regressions | 2,991 |
| C1v version regressions | 0 |
| C3r ordered late accepts | 9 |
| C4 stable replays | 165 |
| C4 mismatched replays | 0 |
| C3r after-grant d=0 late accepts | 100 |

The comparator reports zero metric mismatches against the SQLite model under shared scripted schedules. The workflow reports 53 passing tests. This audit does not turn scheduled outcomes into independent failure-rate estimates.
