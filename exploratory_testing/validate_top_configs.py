#!/usr/bin/env python3
"""
Validate top-performing configs by collecting 20 additional samples each.
Compare actual precision/recall to Bayesian model predictions.
"""

import json
from pathlib import Path
from test_bayesian import (
    PromptConfig,
    run_single_trial,
    load_ground_truth,
)
import llm


def load_top_configs(n=5):
    """Load top N configs by mean precision from bayesian_analysis.json."""
    analysis_file = Path(__file__).parent / "bayesian_analysis.json"
    with open(analysis_file, "r") as f:
        analysis = json.load(f)

    config_results = analysis["config_results"]

    # Sort by mean precision
    sorted_configs = sorted(
        config_results.items(), key=lambda x: x[1]["mean_precision"], reverse=True
    )

    top_configs = []
    for config_idx_str, stats in sorted_configs[:n]:
        config_idx = int(config_idx_str)
        config_dict = stats["config"]

        # Convert to PromptConfig
        config = PromptConfig(
            use_arrow_format=config_dict["arrow_format"],
            use_structured_output=config_dict["structured_output"],
            avoid_style=config_dict["avoid_style"],
            scope_restriction=config_dict["scope_restriction"],
            use_confidence=config_dict["use_confidence"],
            prioritize_precision=config_dict["prioritize_precision"],
            use_reasoning=config_dict["use_reasoning"],
        )

        top_configs.append(
            {
                "config_idx": config_idx,
                "config": config,
                "predicted_precision": stats["mean_precision"],
                "predicted_std": stats["std_precision"],
            }
        )

    return top_configs


def main():
    """Validate top 5 configs with 20 samples each."""
    print("Validating Top 5 Configurations")
    print("=" * 70)

    # Load test document
    test_file = Path(__file__).parent / "test"
    with open(test_file, "r", encoding="utf-8") as f:
        test_text = f.read()
    test_excerpt = "\n".join(test_text.split("\n")[:100])

    # Load ground truth
    ground_truth = load_ground_truth()
    true_error_lines = ground_truth["true_errors"]
    print(f"Ground truth: {len(true_error_lines)} true errors at lines {sorted(true_error_lines)}\n")

    # Get model
    model = llm.get_model()
    print(f"Using model: {model.model_id}\n")

    # Load top configs
    top_configs = load_top_configs(n=5)

    print("Top 5 configurations by Bayesian model prediction:")
    for i, cfg in enumerate(top_configs, 1):
        print(
            f"{i}. Config {cfg['config_idx']}: "
            f"predicted precision = {cfg['predicted_precision']:.3f} ± {cfg['predicted_std']:.3f}"
        )
        print(f"   Factors: {cfg['config'].to_dict()}")

    print("\n" + "=" * 70)
    print("Running 20 validation trials per config...")
    print("=" * 70 + "\n")

    all_results = []
    num_trials = 20

    for cfg_info in top_configs:
        config_idx = cfg_info["config_idx"]
        config = cfg_info["config"]
        predicted_precision = cfg_info["predicted_precision"]

        print(f"\nConfig {config_idx} (predicted precision: {predicted_precision:.3f})")
        print("-" * 70)

        trial_results = []

        for trial in range(1, num_trials + 1):
            print(f"  Trial {trial}/{num_trials}...", end=" ", flush=True)

            try:
                issues = run_single_trial(config, test_excerpt, model)

                # Compute precision/recall
                detected_lines = {issue.line_number for issue in issues if issue.line_number}
                true_positives = detected_lines & true_error_lines
                false_positives = detected_lines - true_error_lines

                precision = len(true_positives) / len(detected_lines) if detected_lines else 0
                recall = len(true_positives) / len(true_error_lines) if true_error_lines else 0

                trial_results.append(
                    {
                        "trial": trial,
                        "issues_found": len(issues),
                        "detected_lines": list(detected_lines),
                        "true_positives": list(true_positives),
                        "false_positives": list(false_positives),
                        "precision": precision,
                        "recall": recall,
                    }
                )

                print(f"{len(issues)} issues, P={precision:.2f}, R={recall:.2f}")

            except Exception as e:
                print(f"ERROR: {e}")
                import traceback
                traceback.print_exc()

        # Compute statistics
        if trial_results:
            precisions = [r["precision"] for r in trial_results]
            recalls = [r["recall"] for r in trial_results]

            import statistics
            mean_precision = statistics.mean(precisions)
            std_precision = statistics.stdev(precisions) if len(precisions) > 1 else 0
            mean_recall = statistics.mean(recalls)

            print(f"\n  Actual results:")
            print(f"    Precision: {mean_precision:.3f} ± {std_precision:.3f}")
            print(f"    Recall:    {mean_recall:.3f}")
            print(f"    Predicted: {predicted_precision:.3f} ± {cfg_info['predicted_std']:.3f}")
            print(f"    Difference: {mean_precision - predicted_precision:+.3f}")

            all_results.append(
                {
                    "config_idx": config_idx,
                    "config": cfg_info["config"].to_dict(),
                    "predicted_precision": predicted_precision,
                    "predicted_std": cfg_info["predicted_std"],
                    "actual_precision": mean_precision,
                    "actual_std": std_precision,
                    "actual_recall": mean_recall,
                    "trials": trial_results,
                }
            )

    # Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    for result in all_results:
        predicted = result["predicted_precision"]
        actual = result["actual_precision"]
        diff = actual - predicted

        print(
            f"Config {result['config_idx']}: "
            f"Predicted={predicted:.3f}, Actual={actual:.3f}, Diff={diff:+.3f}"
        )

    # Save results
    results_file = Path(__file__).parent / "validation_results.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\nValidation results saved to {results_file}")


if __name__ == "__main__":
    main()
