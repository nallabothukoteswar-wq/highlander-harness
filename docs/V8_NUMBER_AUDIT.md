# v8 result-number audit

Before: raw CSV at commit `7468239`. After: regenerated `paper/supplementary/sqlite_trials.csv`. All observed counts below are computed from those CSVs. The changed sweep is a correction to event ordering, not a measured performance improvement.

## Table VI

| Condition | Metric | Before | After |
| --- | --- | ---: | ---: |
| C1 | nD | 1 | 1 |
| C1 | nO | 30 | 30 |
| C1 | duplicates | 100 | 100 |
| C1 | version | 2,071 | 2,071 |
| C1 | epoch | N/A | N/A |
| C1 | late | N/A | N/A |
| C1 | rejected | 0 | 0 |
| C1u | nD | 1 | 1 |
| C1u | nO | 30 | 30 |
| C1u | duplicates | 0 | 0 |
| C1u | version | 2,071 | 2,071 |
| C1u | epoch | N/A | N/A |
| C1u | late | N/A | N/A |
| C1u | rejected | 0 | 0 |
| C1v | nD | N/A | N/A |
| C1v | nO | 30 | 30 |
| C1v | duplicates | N/A | N/A |
| C1v | version | 0 | 0 |
| C1v | epoch | N/A | N/A |
| C1v | late | N/A | N/A |
| C1v | rejected | 2,071 | 2,071 |
| C2 | nD | 1 | 1 |
| C2 | nO | 30 | 30 |
| C2 | duplicates | 100 | 100 |
| C2 | version | 2,071 | 2,071 |
| C2 | epoch | 2,991 | 2,991 |
| C2 | late | N/A | N/A |
| C2 | rejected | 0 | 0 |
| C2f | nD | 1 | 1 |
| C2f | nO | 30 | 30 |
| C2f | duplicates | 0 | 0 |
| C2f | version | 0 | 0 |
| C2f | epoch | 0 | 0 |
| C2f | late | N/A | N/A |
| C2f | rejected | 3,000 | 3,000 |
| C3 | nD | 1 | 1 |
| C3 | nO | 30 | 30 |
| C3 | duplicates | 0 | 0 |
| C3 | version | 0 | 0 |
| C3 | epoch | 0 | 0 |
| C3 | late | 0 | 0 |
| C3 | rejected | 3,000 | 3,000 |
| C3r | nD | 1 | 1 |
| C3r | nO | 30 | 30 |
| C3r | duplicates | 0 | 0 |
| C3r | version | 0 | 0 |
| C3r | epoch | 0 | 0 |
| C3r | late | 9 | 9 |
| C3r | rejected | 2,991 | 2,991 |
| C4 | nD | 1 | 1 |
| C4 | nO | 30 | 30 |
| C4 | duplicates | 0 | 0 |
| C4 | version | 0 | 0 |
| C4 | epoch | 0 | 0 |
| C4 | late | N/A | N/A |
| C4 | rejected | 3,000 | 3,000 |

## Table VII

| Condition | Metric | Before | After |
| --- | --- | ---: | ---: |
| C2f | n | 30 | 30 |
| C2f | lost | 165 | 165 |
| C2f | accepted | 165 | 165 |
| C2f | rejected | 0 | 0 |
| C2f | stable | 0 | 0 |
| C2f | mismatch | 0 | 0 |
| C3 | n | 30 | 30 |
| C3 | lost | 165 | 165 |
| C3 | accepted | 0 | 0 |
| C3 | rejected | 165 | 165 |
| C3 | stable | 0 | 0 |
| C3 | mismatch | 0 | 0 |
| C4 | n | 30 | 30 |
| C4 | lost | 165 | 165 |
| C4 | accepted | 0 | 0 |
| C4 | rejected | 0 | 0 |
| C4 | stable | 165 | 165 |
| C4 | mismatch | 0 | 0 |

## Figure 5, after-grant sweep

| Condition | Delay (s) | Before accepts / attempts | After accepts / attempts |
| --- | ---: | ---: | ---: |
| C3 | 0 | 0/100 | 0/100 |
| C3 | 1 | 0/100 | 0/100 |
| C3 | 5 | 0/100 | 0/100 |
| C3r | 0 | 1/100 | 100/100 |
| C3r | 1 | 1/100 | 100/100 |
| C3r | 5 | 0/100 | 0/100 |

## Abstract and inputs

| Item | Before | After |
| --- | ---: | ---: |
| Abstract numeric remote late-accept claim | Omitted | Omitted |
| Ordered C3r late accepts (reported in V-C) | 9 | 9 |
| Keys per run | 100 | 100 |
| Ordered runs per condition | 30 | 30 |
| Duplicate runs per condition | 1 | 1 |
| Replay runs per condition | 30 | 30 |
| After-grant runs per cell | 1 | 1 |
| Successor first probability | 0.7 | 0.7 |
| Acknowledgment loss probability | 0.05 | 0.05 |
| First-write delay (s) | 2 | 2 |

Other capacity numbers in the abstract are analytical illustration inputs; the v8 change does not modify that model.
