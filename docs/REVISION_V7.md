# Highlander v7 change log

This log maps the supplied v7 review items to the published source-and-paper commit [`4ad94e0`](https://github.com/nallabothukoteswar-wq/highlander-harness/commit/4ad94e0146349d07873299dd1c56e7817b038019). The companion numeric comparison is [`V7_NUMBER_AUDIT.md`](V7_NUMBER_AUDIT.md); its old values are from v6 commit `32e0703` and its new values are regenerated from the corrected raw CSV.

| Item | Outcome | Published change |
| --- | --- | --- |
| A1 | Done | `analysis/exploratory_sqlite.py` tracks one remote epoch for the entire feed; the cross-key rejection has a focused test in `tests/test_exploratory_sqlite.py`. |
| A2 | Done | Ordered schedules establish v1, then delayed former v2 and successor v3. Tests cover an accepted v2 before v3 and a rejected v2 after v3 where appropriate. |
| A3 | Done | The pause-duplicate series resubmits as the former holder; the separate lost-ack replay series retries as the current holder. |
| A4 | Done | The pause and after-grant cells each run once; 30 paired, seeded ordered/replay schedules state p=0.7 and p=0.05 as inputs. No bootstrap intervals are reported for those input probabilities. |
| A5 | Done | `analysis/plot_exploratory.py` plots only observed delay markers, without an interpolating segment, in the manuscript serif style. |
| A6 | Open | The scripted schedule has not been run against PostgreSQL functions. The referenced `Highlander_harness_bugfix_for_Devin.md` was unavailable, and PostgreSQL was unavailable in the execution environment. The study is labeled as an SQLite sink-rule model. |
| B1 | Done | The abstract describes the remote-fence timing window qualitatively and identifies the scripted study. |
| B2 | Done | Section V-C, Tables VI/VII and Fig. 5 were regenerated to reflect the former/current caller, v1<v2<v3, feed-wide epoch and scheduled-run counts. |
| B3 | Done | Spurious bootstrap intervals and fault-validity labels were removed; the input probabilities and raw outcome counts are reported. |
| B4 | Done | Section IV-A calls the PostgreSQL testbed planned; V-C describes the SQLite holder/epoch rule model. |
| B5 | Done as scope statement | The manuscript does not claim PostgreSQL tests passed. Running and repairing that suite remains open. |
| B6 | Pending venue | The compiled IEEEtran paper is seven letter-sized pages. A venue was not specified, so its submission page limit cannot yet be checked. |

## Reproduction and verification

From the repository root, run `python3 -m unittest tests.test_exploratory_sqlite -q`, `python3 -m analysis.exploratory_sqlite --output paper/supplementary`, `python3 -m analysis.plot_exploratory`, and `python3 -m analysis.render_sqlite_results --old-ref 32e07037bb6a8f8d372e474222b8d5e140a32d12`. Build from `paper/` with `pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex` (repeat for cross-references). The focused nine-test suite passed locally; the PDF was inspected and has seven pages. The PostgreSQL/kind campaign and performance, downtime, and cost measurements remain unrun.
