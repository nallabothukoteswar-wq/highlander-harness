# Highlander v8 change log

The v8 code, data, manuscript and PDF were published in [`2e256ec`](https://github.com/nallabothukoteswar-wq/highlander-harness/commit/2e256ec9938d16aa32adc1c3f99e7c19e9eb6ac9). The generated [v8 numeric audit](V8_NUMBER_AUDIT.md) compares the v7 and v8 raw CSVs cell by cell.

| Review item | Status | Change in `2e256ec` |
| --- | --- | --- |
| 1. After-grant timing | Complete | `one_after_grant` orders whole former and successor batches by declared event time. Tests assert the remote and co-located outcomes at every configured resume delay. The raw and summary CSVs and Figure 5 were regenerated. |
| 2a. Sweep text | Complete | Section V-C describes batch ordering and uses values generated from raw rows. |
| 2b. Ordered-series text | Complete | Section V-C states that the ordered workload uses shuffled key-wise interleaving and explains why its remote-fence count differs from the batched sweep. |
| 2c. Scope and Tables VI/VII | Complete | The paper retains its limited SQLite scope. Both tables were regenerated without a manual numeric edit; the audit confirms their outcomes remain unchanged. |
| 3. PostgreSQL harness | Open | The requested `Highlander_harness_bugfix_for_Devin.md` was not attached or found by exact-title search. PostgreSQL and Docker were not available in this workspace. No claim of a green PostgreSQL suite, actual-protocol schedule run or CI result is made. |
| 4. Venue page limit | Open | The compiled manuscript is seven pages. No target venue was supplied, so its page limit cannot yet be checked. |

Verification: `python3 -m unittest tests.test_exploratory_sqlite -q` passed all focused tests; the corrected sweep, raw CSVs, tables, figure and seven-page IEEEtran PDF were regenerated, and the PDF layout was inspected. The broader `tests.test_stats` import requires `pytest`, which was unavailable here; this is not a PostgreSQL protocol test result.
