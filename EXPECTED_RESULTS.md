# Numerical reference

The following values are reconstructed from event exports. Reference predictions in `data/expected.json` are used only after fitting, for final checks.

| Result | Reference |
|---|---|
| Qualified blocks | 45 |
| Excluded blocks | `d8-b02-ab`, `d8-b16-ab`, `d8-b16-ba` |
| Qualified alert counts, E00/A/B/joint | 0, 0, 5, 14 |
| Qualified contrast | 20.0 pp |
| Block-bootstrap interval | [6.666666666666667, 33.33333333333333] pp, within floating-point tolerance |
| All-48 alert counts | 0, 0, 5, 14 |
| All-48 descriptive contrast | 18.75 pp |
| Whole excluded blocks unknown, bounds | [6.25, 31.25] pp |
| Gold / stricter gold | 11 / 9 |
| Eligible landmark runs / later alerts | 44 / 13 |
| Quiet landmark runs | 31 |
| Hot-row AUC | 0.8684863523573201 |
| Unfiltered AUC | 0.8684863523573201 |
| Three-feature AUC | 0.8684863523573201 |
| Conditional AUC interval | [0.7443548387096774, 0.9578163771712159] |

The F1 bootstrap uses 10,000 whole-block draws, seed 20271118. The AUC interval uses 5,000 within-class draws of fixed leave-one-out predictions, also seed 20271118. These intervals do not include the uncertainty sources described in the manuscript's validity discussion.

The script also reports per-arm missing-completion bounds and before/after-amendment diagnostics. These are diagnostic outputs, not independent replications or the manuscript's main estimand. Before/after comparisons confound time, recovery, and deployment.
