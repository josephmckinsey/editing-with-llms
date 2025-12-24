#!/usr/bin/env python3
"""
Bayesian analysis of Phase 1 results using hierarchical modeling.
Implements the model: logit(p_{l,s}) = α + u_l + u_{s_i} + u_{s_o} + u_{s_d} + u_{s_s} + u_{s_c} + u_{s_a} + u_{s_r}

where:
- u_{s_i}: effect of arrow format input
- u_{s_o}: effect of structured output
- u_{s_d}: effect of "avoid style" direction
- u_{s_s}: effect of scope restriction
- u_{s_c}: effect of confidence filtering
- u_{s_a}: effect of precision prioritization
- u_{s_r}: effect of reasoning tokens
"""

import json
import numpy as np
import pymc as pm
from pathlib import Path
from typing import Dict, List, Tuple


def load_phase1_results() -> Dict:
    """Load Phase 1 results from JSON."""
    results_file = Path(__file__).parent / "bayesian_phase1.json"
    with open(results_file, "r") as f:
        data = json.load(f)
    return data


def load_ground_truth() -> set:
    """Load ground truth error line numbers."""
    truth_file = Path(__file__).parent / "true_errors.json"
    with open(truth_file, "r") as f:
        data = json.load(f)
    return {error["line"] for error in data["errors"]}


def extract_factor_values(config_dict: Dict[str, bool]) -> np.ndarray:
    """
    Extract the 7 binary factor values from a config dictionary.

    Returns array of shape (7,) with 0/1 values for:
    [arrow_format, structured_output, avoid_style, scope_restriction,
     use_confidence, prioritize_precision, use_reasoning]
    """
    return np.array([
        int(config_dict["arrow_format"]),
        int(config_dict["structured_output"]),
        int(config_dict["avoid_style"]),
        int(config_dict["scope_restriction"]),
        int(config_dict["use_confidence"]),
        int(config_dict["prioritize_precision"]),
        int(config_dict["use_reasoning"]),
    ])


def prepare_data_for_model(results: List[Dict], true_errors: set) -> Tuple:
    """
    Prepare data for PyMC hierarchical model with factor decomposition.

    Returns:
        - observations: array of shape (n_samples,) with 0/1 for each (location, config) pair
        - location_idx: array of location indices
        - factor_matrix: array of shape (n_samples, 7) with binary factor values
        - location_map: dict mapping line numbers to indices
        - is_true_error: array indicating if location is a true error
        - all_locations: list of all flagged locations
    """
    # Collect all unique locations that were flagged at least once
    all_flagged_locations = set()
    for result in results:
        all_flagged_locations.update(result["detected_lines"])

    # Create location mapping (line_number -> index)
    all_locations = sorted(all_flagged_locations)
    location_map = {loc: idx for idx, loc in enumerate(all_locations)}
    n_locations = len(all_locations)

    # Track which locations are true errors
    is_true_error = np.array([loc in true_errors for loc in all_locations], dtype=int)

    # Create observation data
    observations = []
    location_indices = []
    factor_matrices = []

    for result in results:
        config_factors = extract_factor_values(result["config"])
        detected_lines = set(result["detected_lines"])

        # For each location, record whether it was detected
        for loc in all_locations:
            loc_idx = location_map[loc]
            detected = 1 if loc in detected_lines else 0

            observations.append(detected)
            location_indices.append(loc_idx)
            factor_matrices.append(config_factors)

    return (
        np.array(observations),
        np.array(location_indices),
        np.array(factor_matrices),  # Shape: (n_observations, 7)
        location_map,
        is_true_error,
        all_locations,
    )


def build_hierarchical_model(observations, location_idx, factor_matrix, n_locations):
    """
    Build PyMC hierarchical model with factor decomposition:
    logit(p_{l,s}) = α + u_l + u_{s_i} + u_{s_o} + u_{s_d} + u_{s_s} + u_{s_c} + u_{s_a} + u_{s_r}

    Priors:
    - α ~ N(0, 5)
    - u_l ~ N(0, σ_loc)
    - u_{s_*} ~ N(0, σ_sys)
    - σ_loc, σ_sys ~ Exponential(5)
    """
    with pm.Model() as model:
        # Hyperpriors for variance components
        σ_loc = pm.Exponential("σ_loc", lam=5)
        σ_sys = pm.Exponential("σ_sys", lam=5)

        # Global intercept
        α = pm.Normal("α", mu=0, sigma=5)

        # Location-specific random effects
        u_l = pm.Normal("u_l", mu=0, sigma=σ_loc, shape=n_locations)

        # Factor-specific effects (7 factors)
        factor_names = ["u_s_i", "u_s_o", "u_s_d", "u_s_s", "u_s_c", "u_s_a", "u_s_r"]
        u_factors = []
        for fname in factor_names:
            u_factors.append(pm.Normal(fname, mu=0, sigma=σ_sys))

        u_factors_array = pm.math.stack(u_factors)  # Shape: (7,)

        # Linear predictor (logit scale)
        # logit_p = α + u_l[location_idx] + sum of active factor effects
        factor_contribution = pm.math.dot(factor_matrix, u_factors_array)  # (n_obs,)
        logit_p = α + u_l[location_idx] + factor_contribution

        # Likelihood
        p = pm.Deterministic("p", pm.math.invlogit(logit_p))
        y_obs = pm.Bernoulli("y_obs", p=p, observed=observations)

    return model


def prior_predictive_check(n_locations=50, n_samples=1000):
    """
    Sample from the prior to check if our priors are reasonable.

    Returns statistics about prior predictions for detection probabilities and precision.
    """
    print("\n" + "=" * 70)
    print("PRIOR PREDICTIVE CHECK")
    print("=" * 70)

    # Simulate priors
    np.random.seed(42)

    # Hyperpriors
    σ_loc_samples = np.random.exponential(scale=1/5, size=n_samples)
    σ_sys_samples = np.random.exponential(scale=1/5, size=n_samples)

    print(f"\nHyperprior samples (n={n_samples}):")
    print(f"  σ_loc: mean={σ_loc_samples.mean():.3f}, median={np.median(σ_loc_samples):.3f}, "
          f"range=[{σ_loc_samples.min():.3f}, {σ_loc_samples.max():.3f}]")
    print(f"  σ_sys: mean={σ_sys_samples.mean():.3f}, median={np.median(σ_sys_samples):.3f}, "
          f"range=[{σ_sys_samples.min():.3f}, {σ_sys_samples.max():.3f}]")

    # Sample detection probabilities for a few example configs
    # Let's check: (1) all factors off, (2) all factors on, (3) random config

    configs_to_check = [
        ("All factors OFF", np.zeros(7)),
        ("All factors ON", np.ones(7)),
        ("Random config", np.random.randint(0, 2, size=7)),
    ]

    print("\nPrior predictive detection probabilities:")

    for config_name, config_factors in configs_to_check:
        # Sample one example from the prior
        α = np.random.normal(0, 5, size=n_samples)
        u_l = np.random.normal(0, σ_loc_samples[:, None], size=(n_samples, n_locations))
        u_factors = np.random.normal(0, σ_sys_samples[:, None], size=(n_samples, 7))

        # Compute logit(p) for a random location
        location_idx = n_locations // 2  # Middle location
        factor_contribution = (config_factors * u_factors).sum(axis=1)
        logit_p = α + u_l[:, location_idx] + factor_contribution
        p = 1 / (1 + np.exp(-logit_p))

        print(f"\n  {config_name}:")
        print(f"    Detection prob: mean={p.mean():.3f}, median={np.median(p):.3f}, "
              f"range=[{p.min():.3f}, {p.max():.3f}]")
        print(f"    Fraction p > 0.8: {(p > 0.8).mean():.3f}")
        print(f"    Fraction p < 0.2: {(p < 0.2).mean():.3f}")

    # Check implied prior on precision
    # Assume half of locations are true errors
    print("\n" + "-" * 70)
    print("Prior predictive precision (assuming 50% of locations are true errors):")

    n_true_errors = n_locations // 2
    is_true_error = np.zeros(n_locations, dtype=bool)
    is_true_error[:n_true_errors] = True

    # Sample for a random config
    config_factors = np.random.randint(0, 2, size=7)
    α = np.random.normal(0, 5, size=n_samples)
    u_l = np.random.normal(0, σ_loc_samples[:, None], size=(n_samples, n_locations))
    u_factors = np.random.normal(0, σ_sys_samples[:, None], size=(n_samples, 7))

    factor_contribution = (config_factors * u_factors).sum(axis=1)
    logit_p = α[:, None] + u_l + factor_contribution[:, None]
    p_all = 1 / (1 + np.exp(-logit_p))  # (n_samples, n_locations)

    # Compute precision for each sample
    numerator = p_all[:, is_true_error].sum(axis=1)
    denominator = p_all.sum(axis=1)
    precision_prior = numerator / denominator

    print(f"  Precision: mean={precision_prior.mean():.3f}, median={np.median(precision_prior):.3f}")
    print(f"  P(precision > 0.8): {(precision_prior > 0.8).mean():.3f}")
    print(f"  P(precision < 0.2): {(precision_prior < 0.2).mean():.3f}")

    print("\n" + "=" * 70)
    print("Assessment:")
    print("  - If detection probs are mostly extreme (>0.8 or <0.2), priors are too informative")
    print("  - If prior precision is far from 0.5, model has strong prior beliefs")
    print("  - Ideally, priors should be weakly informative and centered around uncertainty")
    print("=" * 70)

    return {
        "σ_loc_samples": σ_loc_samples,
        "σ_sys_samples": σ_sys_samples,
        "precision_prior": precision_prior,
    }


def run_mcmc(model, samples=2000, tune=1000, chains=4):
    """Run MCMC sampling."""
    with model:
        trace = pm.sample(samples, tune=tune, chains=chains, return_inferencedata=True)
    return trace


def compute_precision_and_recall_for_config(trace, config_dict, is_true_error, n_locations):
    """
    Compute posterior distributions of precision AND recall for a specific configuration.

    Precision = sum over true errors of p_l / sum over all locations of p_l
    Recall = sum over true errors of p_l / number of true errors
    """
    # Extract factor values for this config
    config_factors = extract_factor_values(config_dict)

    # Extract posterior samples
    α_samples = trace.posterior["α"].values  # (chains, samples)
    u_l_samples = trace.posterior["u_l"].values  # (chains, samples, locations)

    # Extract factor effect samples
    factor_names = ["u_s_i", "u_s_o", "u_s_d", "u_s_s", "u_s_c", "u_s_a", "u_s_r"]
    factor_samples = []
    for fname in factor_names:
        factor_samples.append(trace.posterior[fname].values)  # (chains, samples)

    # Flatten chain and sample dimensions
    n_chains, n_samples = α_samples.shape
    α_flat = α_samples.reshape(-1)  # (chains*samples,)
    u_l_flat = u_l_samples.reshape(-1, n_locations)  # (chains*samples, locations)

    factor_samples_flat = [f.reshape(-1) for f in factor_samples]  # Each: (chains*samples,)

    # Compute factor contribution for this config
    factor_contribution = sum(
        config_factors[i] * factor_samples_flat[i] for i in range(7)
    )  # (chains*samples,)

    # Compute p_{l,s} for all locations
    # logit(p) = α + u_l + factor_contribution
    logit_p = α_flat[:, None] + u_l_flat + factor_contribution[:, None]
    p_ls = 1 / (1 + np.exp(-logit_p))  # (n_posterior_samples, n_locations)

    # Compute precision and recall for each posterior sample
    true_error_mask = is_true_error.astype(bool)
    n_true_errors = true_error_mask.sum()

    numerator = p_ls[:, true_error_mask].sum(axis=1)  # Sum over true errors
    denominator = p_ls.sum(axis=1)  # Sum over all locations

    precision = numerator / np.maximum(denominator, 1e-10)
    recall = numerator / n_true_errors  # Expected number of true errors detected / total true errors

    return precision, recall


def analyze_all_configs(trace, is_true_error, n_locations, min_recall=0.1):
    """
    Compute P(PREC_s > 0.8 AND RECALL_s > min_recall) for all 128 configurations.

    Args:
        min_recall: Minimum recall threshold (default 0.1 = 10%)
    """
    results = {}

    for config_idx in range(128):
        # Reconstruct config dict from index
        config_dict = {
            "arrow_format": bool(config_idx & 1),
            "structured_output": bool(config_idx & 2),
            "avoid_style": bool(config_idx & 4),
            "scope_restriction": bool(config_idx & 8),
            "use_confidence": bool(config_idx & 16),
            "prioritize_precision": bool(config_idx & 32),
            "use_reasoning": bool(config_idx & 64),
        }

        precision_posterior, recall_posterior = compute_precision_and_recall_for_config(
            trace, config_dict, is_true_error, n_locations
        )

        # Compute statistics
        prob_high_precision = (precision_posterior > 0.8).mean()
        prob_min_recall = (recall_posterior > min_recall).mean()
        prob_both = ((precision_posterior > 0.8) & (recall_posterior > min_recall)).mean()

        results[config_idx] = {
            "prob_precision_gt_80": prob_high_precision,
            "prob_recall_gt_min": prob_min_recall,
            "prob_both": prob_both,
            "mean_precision": precision_posterior.mean(),
            "std_precision": precision_posterior.std(),
            "median_precision": np.median(precision_posterior),
            "mean_recall": recall_posterior.mean(),
            "std_recall": recall_posterior.std(),
            "median_recall": np.median(recall_posterior),
            "config": config_dict,
        }

    return results


def identify_uncertain_configs(config_results, threshold_low=0.1, threshold_high=0.9):
    """
    Identify configurations that are uncertain (P(PREC > 0.8) not clearly < 0.1 or > 0.9).
    """
    uncertain = []

    for config_idx, stats in config_results.items():
        prob = stats["prob_precision_gt_80"]

        if threshold_low < prob < threshold_high:
            # Measure uncertainty as distance from 0.5 (most uncertain point)
            uncertainty = abs(prob - 0.5)
            uncertain.append((config_idx, uncertainty, prob))

    # Sort by uncertainty (closest to 0.5 = most uncertain)
    uncertain.sort(key=lambda x: x[1])

    return [(idx, prob) for idx, _, prob in uncertain]


def main():
    """Main analysis pipeline."""
    print("Bayesian Analysis: Phase 1 Results")
    print("=" * 70)

    # Load data
    phase1_data = load_phase1_results()
    results = phase1_data["results"]
    true_errors = load_ground_truth()

    print(f"Loaded {len(results)} samples from Phase 1")
    print(f"Ground truth: {len(true_errors)} true errors")

    # Prepare data for modeling
    print("\nPreparing data for hierarchical model...")
    (
        observations,
        location_idx,
        factor_matrix,
        location_map,
        is_true_error,
        all_locations,
    ) = prepare_data_for_model(results, true_errors)

    n_locations = len(all_locations)

    print(f"Total observations: {len(observations)}")
    print(f"Unique locations flagged: {n_locations}")
    print(f"Locations that are true errors: {is_true_error.sum()}")

    # Prior predictive check
    prior_predictive_check(n_locations=n_locations, n_samples=1000)

    print("\nPress Enter to continue with MCMC sampling, or Ctrl+C to adjust priors...")
    input()

    # Build model
    print("\nBuilding hierarchical Bayesian model...")
    print("Model: logit(p) = α + u_l + u_s_i + u_s_o + u_s_d + u_s_s + u_s_c + u_s_a + u_s_r")
    model = build_hierarchical_model(observations, location_idx, factor_matrix, n_locations)

    # Run MCMC
    print("\nRunning MCMC sampling...")
    print("(This may take several minutes)")
    trace = run_mcmc(model, samples=2000, tune=1000, chains=4)

    # Print factor effect summaries
    print("\n" + "=" * 70)
    print("FACTOR EFFECTS (posterior means)")
    print("=" * 70)
    factor_names = [
        ("u_s_i", "Arrow format input"),
        ("u_s_o", "Structured output"),
        ("u_s_d", "Avoid style direction"),
        ("u_s_s", "Scope restriction"),
        ("u_s_c", "Confidence filtering"),
        ("u_s_a", "Prioritize precision"),
        ("u_s_r", "Reasoning tokens"),
    ]

    for fname, description in factor_names:
        samples = trace.posterior[fname].values.flatten()
        mean_effect = samples.mean()
        std_effect = samples.std()
        print(f"{description:25s} ({fname}): {mean_effect:+.3f} ± {std_effect:.3f}")

    # Analyze all configs
    print("\nComputing precision AND recall posteriors for all configurations...")
    print("(Requiring recall > 10% to avoid overly conservative configs)")
    config_results = analyze_all_configs(trace, is_true_error, n_locations, min_recall=0.1)

    # Identify uncertain configs
    uncertain_configs = identify_uncertain_configs(config_results)

    # Summary statistics
    print("\n" + "=" * 70)
    print("CONFIGURATION RESULTS")
    print("=" * 70)

    high_both = sum(1 for s in config_results.values() if s["prob_both"] > 0.9)
    low_both = sum(1 for s in config_results.values() if s["prob_both"] < 0.1)
    high_precision_only = sum(1 for s in config_results.values() if s["prob_precision_gt_80"] > 0.9)
    low_precision = sum(1 for s in config_results.values() if s["prob_precision_gt_80"] < 0.1)
    uncertain = len(uncertain_configs)

    print(f"Configs with P(precision > 0.8 AND recall > 0.1) > 0.9: {high_both}")
    print(f"Configs with P(precision > 0.8 AND recall > 0.1) < 0.1: {low_both}")
    print(f"Configs with P(precision > 0.8 only) > 0.9: {high_precision_only} (likely too conservative)")
    print(f"Configs with P(precision > 0.8) < 0.1: {low_precision}")
    print(f"Uncertain configs (0.1 < P < 0.9): {uncertain}")

    # Show top configs by recall (that still maintain decent precision)
    print("\nTop 5 configurations by recall (mean_precision > 0.2):")
    viable_configs = {k: v for k, v in config_results.items() if v["mean_precision"] > 0.2}
    top_by_recall = sorted(
        viable_configs.items(), key=lambda x: x[1]["mean_recall"], reverse=True
    )[:5]

    for config_idx, stats in top_by_recall:
        print(
            f"  Config {config_idx}: "
            f"recall={stats['mean_recall']:.3f}, "
            f"precision={stats['mean_precision']:.3f}, "
            f"P(both)={stats['prob_both']:.3f}"
        )

    # Show best F1 scores
    print("\nTop 5 configurations by F1 score:")
    configs_with_f1 = []
    for config_idx, stats in config_results.items():
        p = stats["mean_precision"]
        r = stats["mean_recall"]
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0
        configs_with_f1.append((config_idx, f1, p, r, stats))

    top_by_f1 = sorted(configs_with_f1, key=lambda x: x[1], reverse=True)[:5]

    for config_idx, f1, p, r, stats in top_by_f1:
        print(
            f"  Config {config_idx}: "
            f"F1={f1:.3f}, precision={p:.3f}, recall={r:.3f}, "
            f"P(both)={stats['prob_both']:.3f}"
        )

    if uncertain > 0:
        print("\nMost uncertain configurations (need more sampling):")
        for config_idx, prob in uncertain_configs[:10]:
            stats = config_results[config_idx]
            print(
                f"  Config {config_idx}: "
                f"P(prec>0.8)={prob:.3f}, "
                f"mean={stats['mean_precision']:.3f}"
            )

    # Save results
    results_file = Path(__file__).parent / "bayesian_analysis.json"
    with open(results_file, "w") as f:
        json.dump(
            {
                "factor_effects": {
                    fname: {
                        "mean": float(trace.posterior[fname].values.flatten().mean()),
                        "std": float(trace.posterior[fname].values.flatten().std()),
                    }
                    for fname, _ in factor_names
                },
                "config_results": {str(k): v for k, v in config_results.items()},
                "uncertain_configs": [
                    {"config_idx": idx, "prob": prob} for idx, prob in uncertain_configs
                ],
                "summary": {
                    "high_both_count": high_both,
                    "low_both_count": low_both,
                    "high_precision_only_count": high_precision_only,
                    "low_precision_count": low_precision,
                    "uncertain_count": uncertain,
                },
            },
            f,
            indent=2,
        )

    print(f"\nResults saved to {results_file}")


if __name__ == "__main__":
    main()
