# Minimal offline verification artifact

This repository verifies the main D8 results in **How Two "Harmless" Changes Amplify Service Alert Risk**. It includes event-level exports from all **192 runs in 48 four-arm blocks**, including failed runs. It reconstructs eligibility, foreground-defined service alerts, gold cases, the additive alert-risk contrast, and the within-batch landmark models.

Execution needs **no database, containers, network connection, or model API**. This is an offline verification subset, not a complete deployment of the experimental system.

## Quick start

Use **Python 3.11** and the versions in `requirements.txt`:

```sh
python -m pip install -r requirements.txt
python -I reproduce.py --out results
```

Dependency installation may need internet access. The verification itself is offline; if the pinned packages are already installed, skip installation. The tested environment is Python 3.11.4, NumPy 1.24.3, SciPy 1.10.1, and scikit-learn 1.3.0. No GPU is required.

The script checks file hashes before analysis and writes:

- `results/results.json`: reconstructed results and diagnostics;
- `results/blocks.csv`: all blocks, qualification, gold status, and four alert outcomes;
- `results/features.csv`: the 44 eligible joint runs and landmark features.

A successful run exits with code 0. See `EXPECTED_RESULTS.md` for the numerical targets.

## Expected main results

| Quantity | Expected value |
|---|---|
| Attempted / qualified blocks | 48 / 45 |
| Alerting runs: background, A, B, A+B | 0 / 45, 0 / 45, 5 / 45, 14 / 45 |
| Additive interaction contrast | +20.00 percentage points |
| Block-bootstrap 95% interval | [+6.6666666667, +33.3333333333] pp |
| All-attempted descriptive contrast | +18.75 pp |
| Gold / stricter whole-run-control gold | 11 / 9 |
| Landmark sample | 44 runs: 13 later alerts, 31 quiet |
| Hot-row, unfiltered, and three-feature AUC | 0.8684863523573201 |
| Conditional AUC interval | [0.7443548387096774, 0.9578163771712159] |

The four-arm contrast is `p11 - p10 - p01 + p00`, with N1+N2 present in every arm. Gold cases are a stricter subset of alerting joint runs; they are not the outcome used to train the landmark models.

## Repository contents

- `reproduce.py`: offline reconstruction, fitting, and assertions;
- `requirements.txt`: exact dependency versions;
- `SHA256.json`: hashes of the distributed input files, code, and documentation;
- `data/plan.json`: all scheduled runs, block/arm IDs, execution order, and activation slots;
- `data/protocol.json`: recorded thresholds, workload, and protocol settings;
- `data/runs.json`: opening/terminal resource receipts, recovery measurements, fingerprints, and archived checks;
- `data/amendment.json`: stop-rule amendment metadata;
- `data/archived_labels.json`: archived labels, used to check reconstructed qualification and gold decisions;
- `data/expected.json`: archived reference scores, used only for final assertions;
- `data/<run-id>/`: request, window, event, database-sample, and pool-sample exports;
- `ANONYMIZATION.md`: metadata normalization and preservation guarantees.

Each run contains five files:

| File | Recorded information |
|---|---|
| `requests.jsonl` | Scheduled time, completion availability, completion delay from scheduled send, success, latency, dispatch, and list size |
| `windows.json` | All 21 recorded alert windows, request membership, violations, and publications |
| `events.json` | Change bits, effective/receipt times, and configuration readback |
| `db.json` | Sample availability, collection failures, and captured lock edges |
| `pool.json` | Sample availability and available-connection counts |

The source export already replaces request UUIDs with per-run integer positions, consistently in window membership. It excludes HTTP bodies, SQL statements, credentials, and application logs. `source_line` identifies the line in the source event file, not a filesystem path. Some protocol planning fields are inherited; `plan.json` records the actual D8 schedule.

## Reconstruction and interpretation

The verifier replays the alert rule from requests before checking recorded windows. It reconstructs recovery, state restoration, event ordering/readback, measurement quality, block qualification, and gold admission, then checks archived labels. Archived model predictions are read only after feature extraction and fitting, for assertions; they are not inputs to the models.

The 3-second landmark uses samples **available** in `[0,3)` after both A and B have taken effect. Already-alerted runs are excluded. Persistent edges count repeatedly across samples. Standardization and logistic regression are fitted only on each training fold. The confidence interval resamples the resulting leave-one-out predictions within outcome classes and conditions on those predictions.

The hot-row feature and landmark design were prespecified for D8. Counting every captured edge is a post-hoc ablation. In this D8 subset, hot-row and unfiltered counts coincide for all 44 eligible runs; each model is nevertheless fitted explicitly.

## Study boundaries

The schedule and four-arm design were frozen, but the additive-risk analysis was developed after execution. After interim results, the safety stop was changed before execution index 128: originally two consecutive cleanup or recovery failures stopped the campaign; subsequently only resource-cleanup failures counted. Run 126 failed cleanup, run 127 passed cleanup but failed recovery, and an interim report had already recorded 9 gold cases. Failed runs were not replaced. The package retains the failures and amendment metadata.

Qualification includes post-run recovery, so the qualified contrast is conditional on that selection. All-48 outcomes are descriptive recorded attempts. The whole-excluded-block bounds assume unknown outcomes in the three excluded blocks; they are not confidence intervals or estimates under the unamended stopping protocol. The block bootstrap retains within-block dependence, not cross-block temporal or deployment-session effects.

Gold admission requires pre-alert hot-row and pool evidence. Reconstructing gold membership is not an independent test of those signals' sensitivity. The foreground-defined landmark outcome does not use either signal. This artifact verifies in-batch results, not independent predictive generalization or a production warning system.

This subset does not reproduce pooled D6/D7 results, attribution/LLM outputs, calibration campaigns, deployment, or production anecdotes. It replays archived resource receipts rather than re-running cleanup. Timestamp consistency is checked within the exports; external clock synchronization and omitted source files cannot be independently revalidated here.
