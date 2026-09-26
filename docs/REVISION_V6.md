# Revision v6 change log

| Brief item | Edit and location |
| --- | --- |
| 1.1 | Separate version and epoch regressions in manuscript Section V-B, Table V, full-width Table VI, and Section VI; define separate SQL views in `sql/07_views.sql`, metrics in `docs/PROTOCOL.md`, and hypotheses in `analysis/hypotheses.yaml`. The old combined SQL view remains solely for compatibility with existing tests. |
| 1.2 | Define fault-free Series D lost-ack retries (5%, 50 ms, C2f/C3/C4, 30 trials) in Section V-B; report controlled retry outcomes in Table VII and declare retry delay in `runner/series/d_replay.py`. Set default `LOST_ACK_RATE=0` outside explicitly configured Series D. |
| 1.3 | Define after-grant first-write delay of 2 s, C3/C3r timing predictions and ordered C3r sweep cells in Section V-B; plot controlled after-grant outcomes in Fig. 5 and declare `first_write_delay_s` in `runner/series/c_late.py`. The cluster trial runner does not yet enforce this delay. |
| 1.4 | No registration exists in this repository; the original Fig. 7 placeholder was replaced by an observed, explicitly scoped Fig. 5 without a registration claim. |
| 1.5 | Make Table VI a legible full-width `table*`, with separate regression columns and spacing before its note. |
| 1.6 | Clarify the co-located fence wording in Section IV-B. |
| Repository correction | Update artifact availability in Section V-D with the public repository address and disclose incomplete runner and analysis scripts. Fix Python syntax errors in `analysis/stats.py` and `tests/test_stats.py`. |

The requested `docs/PAPER_METHODS.md` does not exist in this checkout, so parameter-by-parameter reconciliation with that document is pending. No full-campaign raw CSVs, archival DOI or preregistration were present at revision time. A subsequent controlled SQLite study generated its own raw and summary CSVs, filled the manuscript's observed mechanism tables, and removed result placeholders. These rows are not outputs from the planned cluster campaign.

Verification: `pdflatex` completed with no unresolved citations or overfull boxes (seven pages); `python3 -m compileall -q analysis tests runner worker` passed. Five focused SQLite checks passed. Full protocol tests could not run in this environment because `pytest` and `psycopg` are unavailable. No cluster campaign or performance measurements were run.
