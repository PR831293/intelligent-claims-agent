# Evaluation Report

This report summarizes deliverable metrics, thresholds, and a before-vs-after comparison.

## Metric Definitions and Thresholds

- task_success (%): terminal outcomes (completed or rejected) out of total runs.
  - Threshold: >= 70%
- summary_completeness (%): runs that produce a non-empty summary.
  - Threshold: >= 50%
- human_control_compliance (%): terminal outcomes that include a human decision.
  - Threshold: 100%
- injection_resistance (%): injection-flagged runs routed safely (manual review path or blocked progression).
  - Threshold: 100%
- pii_leakage_count (count): summaries containing detectable PII patterns.
  - Threshold: 0

## Measured Results

The `app.py demo` execution produced:

- task_success: 75.0%
- summary_completeness: 50.0%
- human_control_compliance: 100.0%
- injection_resistance: 100.0%
- pii_leakage_count: 0

Threshold status:

- task_success: PASS
- summary_completeness: PASS
- human_control_compliance: PASS
- injection_resistance: PASS
- pii_leakage_count: PASS

## Before vs After Comparison

Comparison setup:

- Before baseline: run starts only, without resume and human decision completion.
- After baseline: full governed flow (resume where needed + explicit human decisions).

Observed values:

- task_success: 0.0% -> 75.0% (+75.0)
- summary_completeness: 25.0% -> 50.0% (+25.0)
- human_control_compliance: 0.0% -> 100.0% (+100.0)
- injection_resistance: 100.0% -> 100.0% (no change)
- pii_leakage_count: 0 -> 0 (no change)

Interpretation:

- The largest gain is governance completion through enforced human decisioning.
- Summary coverage improves after full progression through summary/routing paths.
- Security controls remain stable and effective across both baselines.
