# v7 result-number audit

The before values come from the publicly published v6 commit; the after values come from regenerated `sqlite_trials.csv`. Every table cell below was counted from those CSVs. N/A means the metric was not applicable. The schedules differ, so a change is a correction to the model, not a performance improvement.

## Table VI

| Condition | Metric | Before | After |
| --- | --- | ---: | ---: |
| C1 | nD | 30 | 1 |
| C1 | nO | 30 | 30 |
| C1 | duplicates | 3,000 | 100 |
| C1 | version | 3,000 | 2,071 |
| C1 | epoch | N/A | N/A |
| C1 | late | N/A | N/A |
| C1 | rejected | 0 | 0 |
| C1u | nD | 30 | 1 |
| C1u | nO | 30 | 30 |
| C1u | duplicates | 0 | 0 |
| C1u | version | 3,000 | 2,071 |
| C1u | epoch | N/A | N/A |
| C1u | late | N/A | N/A |
| C1u | rejected | 0 | 0 |
| C1v | nD | N/A | N/A |
| C1v | nO | 30 | 30 |
| C1v | duplicates | N/A | N/A |
| C1v | version | 0 | 0 |
| C1v | epoch | N/A | N/A |
| C1v | late | N/A | N/A |
| C1v | rejected | 3,000 | 2,071 |
| C2 | nD | 30 | 1 |
| C2 | nO | 30 | 30 |
| C2 | duplicates | 3,000 | 100 |
| C2 | version | 3,000 | 2,071 |
| C2 | epoch | 2,067 | 2,991 |
| C2 | late | N/A | N/A |
| C2 | rejected | 0 | 0 |
| C2f | nD | 30 | 1 |
| C2f | nO | 30 | 30 |
| C2f | duplicates | 3,000 | 0 |
| C2f | version | 0 | 0 |
| C2f | epoch | 0 | 0 |
| C2f | late | N/A | N/A |
| C2f | rejected | 3,000 | 3,000 |
| C3 | nD | 30 | 1 |
| C3 | nO | 30 | 30 |
| C3 | duplicates | 0 | 0 |
| C3 | version | 0 | 0 |
| C3 | epoch | 0 | 0 |
| C3 | late | 0 | 0 |
| C3 | rejected | 3,000 | 3,000 |
| C3r | nD | 30 | 1 |
| C3r | nO | 30 | 30 |
| C3r | duplicates | 0 | 0 |
| C3r | version | 933 | 0 |
| C3r | epoch | 0 | 0 |
| C3r | late | 933 | 9 |
| C3r | rejected | 2,067 | 2,991 |
| C4 | nD | 30 | 1 |
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

## Abstract and table-caption context

| Item | Before | After |
| --- | ---: | ---: |
| Abstract remote late-accept count | 933 | Omitted; qualitative mechanism claim (new raw count: 9) |
| Table VI duplicate runs per condition | 30 | 1 |
| Table VI ordered runs per condition | 30 | 30 |
| Table VI keys per run | 100 | 100 |
| Table VI caption, invalid trials | 0 by construction | Removed: no fault verification occurs |
| Table VI caption, at-risk submissions per duplicate cell | 3,000 | 100 |
| Table VI caption, at-risk submissions per ordered cell | 3,000 | 3,000 |
| Table VII replay runs per condition | 30 | 30 |
| Table VII configured loss probability | 0.05 | 0.05 |
| Table VII caption, invalid trials | 0 by construction | Removed: no fault verification occurs |
| Table VII response mismatches | 0 | 0 |
| Abstract illustrative capacity, peak requests/s | 600 | 600 |
| Abstract illustrative capacity, safe requests/s per replica | 120 | 120 |
| Abstract illustrative capacity, reserve | 20% | 20% |
| Abstract illustrative capacity, required replicas | 7 | 7 |
| Abstract exploratory schedules per cell | 30 | Omitted (mixed scheduled-run counts) |

The old abstract also reported zero version regressions for C1v and zero epoch regressions for co-located fences; those observations remain zero under the corrected schedule. The old abstract reported the 7-replica capacity illustration from declared 600 requests/s, 120 requests/s per replica and 20% reserve; that calculation is unchanged by the exploratory-study correction.
