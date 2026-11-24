# Metadata normalization

This repository contains a minimal, normalized export for anonymous review.

- All absolute ISO timestamps were translated by the **same constant offset**. The first recorded measurement origin maps to `2000-01-01T00:00:00+00:00`. Earlier setup records can therefore fall in 1999. These are synthetic dates, not the original execution dates. Ordering, elapsed differences, inter-run spacing, and all relative `*_s` values are preserved.
- `recorded_timing` contains the normalized event timestamps. The verifier checks that normalized timestamps and exported relative times agree.
- Application pool object IDs were consistently mapped to small integers. Equality and inequality of opening/terminal IDs are preserved; capacities and availability counts are unchanged.
- Run/block IDs are retained to match the manuscript's cases. Request IDs remain per-run integer positions, as in the input export.
- The omitted-source hash/path manifest is not distributed. It named source files outside this subset, which reviewers could not retrieve from this repository. `SHA256.json` instead verifies the actual files supplied here.

Measured durations, latencies, dispatch delays, relative sample/receipt times, change masks, lock-edge contents, recovery values, outcomes, labels, ordering, random seeds, model settings, and numerical reference scores are unchanged. The analysis code differs from the input verifier only in the name of its root-directory variable and the normalized timing-container name.

Package hashes detect changes to the supplied files. They do not establish authenticity of omitted source files or constitute an external provenance guarantee. Author-side source hashes and export mappings are retained separately and are not needed to execute this package.
