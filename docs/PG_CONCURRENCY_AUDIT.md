# Active-handover PostgreSQL audit

All figures below are derived from `pg_concurrency_trials.csv`, `pg_acquisition_races.csv`, and `pg_concurrency_config.json`.

| Repeat | Condition | Runs | Pre-grant accepted | Post-grant attempts | Late accepts |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | C2f | 30 | 300 | 821 | 0 |
| 0 | C3 | 30 | 298 | 821 | 0 |
| 0 | C4 | 30 | 298 | 823 | 0 |
| 0 | C3r | 30 | 379 | 821 | 77 |
| 1 | C2f | 30 | 300 | 824 | 0 |
| 1 | C3 | 30 | 298 | 821 | 0 |
| 1 | C4 | 30 | 297 | 827 | 0 |
| 1 | C3r | 30 | 370 | 830 | 90 |
| 2 | C2f | 30 | 299 | 830 | 0 |
| 2 | C3 | 30 | 299 | 825 | 0 |
| 2 | C4 | 30 | 303 | 816 | 0 |
| 2 | C3r | 30 | 376 | 824 | 88 |
| 3 | C2f | 30 | 298 | 831 | 0 |
| 3 | C3 | 30 | 296 | 832 | 0 |
| 3 | C4 | 30 | 297 | 828 | 0 |
| 3 | C3r | 30 | 370 | 830 | 89 |
| 4 | C2f | 30 | 297 | 832 | 0 |
| 4 | C3 | 30 | 296 | 832 | 0 |
| 4 | C4 | 30 | 295 | 831 | 0 |
| 4 | C3r | 30 | 371 | 829 | 92 |

C3r late-accept range across repetitions: 77--92.
Fresh-key races: 1,000 single winners at epoch 1.
Expired-lease races: 1,000 single winners at epoch 2, an increment of 1.
