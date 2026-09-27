# Threaded PostgreSQL result audit

Derived from `paper/supplementary/pg_concurrency_trials.csv` and `pg_acquisition_races.csv`; the SQL runner wrote every raw row.

| Condition | Runs | Former attempts | Former accepted | Late accepts |
| --- | ---: | ---: | ---: | ---: |
| C2f | 30 | 600 | 0 | 0 |
| C3 | 30 | 600 | 0 | 0 |
| C4 | 30 | 600 | 0 | 0 |
| C3r | 30 | 600 | 19 | 19 |

Acquisition races: 1,000; rounds with exactly one winner and one grant: 1,000.
