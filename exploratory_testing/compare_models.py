#!/usr/bin/env python3
"""
Compare configs 29, 98, and 106 on Gemini 2.5 Flash vs Gemini 2.5 Pro.
20 trials per (config, model) combination.
"""

import json
from pathlib import Path
from test_bayesian import PromptConfig, run_single_trial, load_ground_truth
import llm


def get_config(config_idx: int) -> PromptConfig:
    """Create PromptConfig from index."""
    return PromptConfig(
        use_arrow_format=bool(config_idx & 1),
        use_structured_output=bool(config_idx & 2),
        avoid_style=bool(config_idx & 4),
        scope_restriction=bool(config_idx & 8),
        use_confidence=bool(config_idx & 16),
        prioritize_precision=bool(config_idx & 32),
        use_reasoning=bool(config_idx & 64),
    )


def main():
    """Compare 3 configs on 2 models."""
    print("Model Comparison: Gemini 2.5 Flash vs Pro")
    print("=" * 70)

    # Configs to test
    test_configs = [
        (29, "Best precision (conservative)"),
        (98, "Best F1 - structured + reasoning"),
        (106, "Best F1 - structured + scope + reasoning"),
    ]

    # Models to test (using OpenRouter)
    models_to_test = [
        ("openrouter/google/gemini-2.5-flash", "Gemini 2.5 Flash"),
        ("openrouter/google/gemini-2.5-pro", "Gemini 2.5 Pro"),
    ]

    # Load test document
    test_file = Path(__file__).parent / "test"
    with open(test_file, "r", encoding="utf-8") as f:
        test_text = f.read()
    test_excerpt = "\n".join(test_text.split("\n")[:100])

    # Load ground truth
    ground_truth = load_ground_truth()
    true_error_lines = ground_truth["true_errors"]
    print(
        f"Ground truth: {len(true_error_lines)} true errors at lines {sorted(true_error_lines)}\n"
    )

    # Show configs
    print("Testing configurations:")
    for config_idx, description in test_configs:
        config = get_config(config_idx)
        print(f"  Config {config_idx}: {description}")
        print(f"    Factors: {config.to_dict()}")

    print("\n" + "=" * 70)
    print("Running 20 trials per (config, model) combination...")
    print("=" * 70 + "\n")

    all_results = []
    num_trials = 20

    for model_id, model_name in models_to_test:
        print(f"\n{'='*70}")
        print(f"MODEL: {model_name} ({model_id})")
        print(f"{'='*70}\n")

        try:
            model = llm.get_model(model_id)
            print(f"Loaded model: {model.model_id}\n")
        except Exception as e:
            print(f"ERROR loading model {model_id}: {e}")
            print("Skipping this model...\n")
            continue

        for config_idx, description in test_configs:
            config = get_config(config_idx)

            print(f"\nConfig {config_idx}: {description}")
            print("-" * 70)

            trial_results = []

            for trial in range(1, num_trials + 1):
                print(f"  Trial {trial}/{num_trials}...", end=" ", flush=True)

                try:
                    issues = run_single_trial(config, test_excerpt, model)

                    # Compute precision/recall
                    detected_lines = {
                        issue.line_number for issue in issues if issue.line_number
                    }
                    true_positives = detected_lines & true_error_lines
                    false_positives = detected_lines - true_error_lines

                    precision = (
                        len(true_positives) / len(detected_lines) if detected_lines else 0
                    )
                    recall = (
                        len(true_positives) / len(true_error_lines)
                        if true_error_lines
                        else 0
                    )

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
                issues_counts = [r["issues_found"] for r in trial_results]

                import statistics

                mean_precision = statistics.mean(precisions)
                std_precision = statistics.stdev(precisions) if len(precisions) > 1 else 0
                mean_recall = statistics.mean(recalls)
                std_recall = statistics.stdev(recalls) if len(recalls) > 1 else 0
                mean_issues = statistics.mean(issues_counts)
                f1 = (
                    2 * mean_precision * mean_recall / (mean_precision + mean_recall)
                    if (mean_precision + mean_recall) > 0
                    else 0
                )

                print(f"\n  Results:")
                print(f"    Precision: {mean_precision:.3f} ± {std_precision:.3f}")
                print(f"    Recall:    {mean_recall:.3f} ± {std_recall:.3f}")
                print(f"    F1 Score:  {f1:.3f}")
                print(f"    Avg issues: {mean_issues:.1f}")

                all_results.append(
                    {
                        "model_id": model_id,
                        "model_name": model_name,
                        "config_idx": config_idx,
                        "config_description": description,
                        "config": config.to_dict(),
                        "mean_precision": mean_precision,
                        "std_precision": std_precision,
                        "mean_recall": mean_recall,
                        "std_recall": std_recall,
                        "f1_score": f1,
                        "mean_issues": mean_issues,
                        "trials": trial_results,
                    }
                )

    # Summary comparison
    print("\n" + "=" * 70)
    print("COMPARISON SUMMARY")
    print("=" * 70)

    # Group by config
    for config_idx, description in test_configs:
        print(f"\nConfig {config_idx}: {description}")
        print("-" * 70)

        config_results = [r for r in all_results if r["config_idx"] == config_idx]

        for result in config_results:
            print(
                f"  {result['model_name']:20s}: "
                f"P={result['mean_precision']:.3f}, "
                f"R={result['mean_recall']:.3f}, "
                f"F1={result['f1_score']:.3f}"
            )

    # Best overall
    print("\n" + "=" * 70)
    print("BEST RESULTS")
    print("=" * 70)

    if all_results:
        best_f1 = max(all_results, key=lambda x: x["f1_score"])
        best_precision = max(all_results, key=lambda x: x["mean_precision"])
        best_recall = max(all_results, key=lambda x: x["mean_recall"])

        print(f"\nBest F1: {best_f1['f1_score']:.3f}")
        print(
            f"  {best_f1['model_name']} + Config {best_f1['config_idx']} ({best_f1['config_description']})"
        )
        print(
            f"  Precision={best_f1['mean_precision']:.3f}, Recall={best_f1['mean_recall']:.3f}"
        )

        print(f"\nBest Precision: {best_precision['mean_precision']:.3f}")
        print(
            f"  {best_precision['model_name']} + Config {best_precision['config_idx']} ({best_precision['config_description']})"
        )
        print(
            f"  Recall={best_precision['mean_recall']:.3f}, F1={best_precision['f1_score']:.3f}"
        )

        print(f"\nBest Recall: {best_recall['mean_recall']:.3f}")
        print(
            f"  {best_recall['model_name']} + Config {best_recall['config_idx']} ({best_recall['config_description']})"
        )
        print(
            f"  Precision={best_recall['mean_precision']:.3f}, F1={best_recall['f1_score']:.3f}"
        )

    # Save results
    results_file = Path(__file__).parent / "model_comparison_results.json"
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n\nResults saved to {results_file}")


if __name__ == "__main__":
    main()
