# Legacy Isolation Forest Charts

These four images were already tracked under `services/isolationForest/trainer/evaluation_results/`. They are retained together as historical artifacts:

- [Confusion matrix](legacy/confusion-matrix.png).
- [Precision-recall curve](legacy/precision-recall-curve.png).
- [ROC curve](legacy/roc-curve.png).
- [Score distribution](legacy/score-distribution.png).

The original run date, training revision, dataset identity, and complete run configuration were not established during organization. Do not use these images as current model-quality evidence. The [trainer evaluator](../../../../services/isolationForest/trainer/evaluation/model_evaluator.py) still creates new plots in its original output directory, which is now ignored. Publish future snapshots only with reproducible run metadata and sanitized inputs.
