# Phase 0 Experiment 2: Confidence and Severity Filtering

## Hypothesis

Adding **confidence** (0-100%) and **severity** (low/medium/high) ratings to LLM outputs will allow us to filter out low-confidence issues, thereby reducing false positives while maintaining recall of real errors.

We hypothesize that:
- LLM will assign **higher confidence** to real errors (like typos and inconsistencies) than to stylistic preferences
- Filtering to **confidence > 80%** will significantly reduce false positive rate
- **High severity** issues will correlate with our known real errors
- This approach will improve precision without sacrificing too much recall

## Previous Results (Experiment 1)

From our first experiment, we learned:
- **Best precision: ~40-50%** (Structured markers + Structured output)
- **All strategies** have 50-65% false positive rate
- High variance across trials (same strategy: 0-17 issues)
- **Real errors found**: Lines 74, 73, 53, 32 (4 total in first 100 lines)

**Key problem**: Half of all flagged issues are false positives, making the tool frustrating to use.

## Method

### Test Document
- Same as Experiment 1: `test` file, first 100 lines

### Input Strategies (2)
1. **Line-numbered (arrow)**: `N→ <line text>` format
2. **Plain text**: No line numbers in input

### Output Strategies (2)
1. **Line citations**: Request format like "Line N: [text] (explanation)"
2. **Structured output**: Request format like "LINE: N\nTEXT: ...\nISSUE: ..."

### New Feature: Confidence and Severity
Both output strategies will now request:
- **Confidence**: 0-100% (how sure the LLM is this is an actual error)
- **Severity**: low/medium/high (how important is this issue)

**Filtering**: We'll filter results to only show issues with **confidence > 80%** (but we won't tell the LLM this threshold).

### Test Combinations (8 total)

For each of 4 strategy combinations (2 inputs × 2 outputs):
1. **Normal version** (no confidence/severity)
2. **Confidence version** (with confidence/severity filtering)

| Input | Output | Confidence? |
|-------|--------|-------------|
| Arrow | Line citations | No |
| Arrow | Line citations | Yes (>80%) |
| Arrow | Structured | No |
| Arrow | Structured | Yes (>80%) |
| Plain text | Line citations | No |
| Plain text | Line citations | Yes (>80%) |
| Plain text | Structured | No |
| Plain text | Structured | Yes (>80%) |

### Execution
```bash
python test_strategies_confidence.py
```

**Trials**: Run **10 trials** per combination for statistical significance.
- Total API calls: 8 combinations × 10 trials = 80 calls (~$0.24)

Results saved to `confidence_test_results.json`

### Evaluation Metrics

For each strategy, we'll measure:
1. **Precision**: Real errors / Total flagged issues (higher is better)
2. **Recall**: Real errors found / 4 known real errors (higher is better)
3. **F1 Score**: Harmonic mean of precision and recall
4. **False Positive Rate**: False positives / Total flagged issues (lower is better)
5. **Mean issues found**: Average across 10 trials
6. **Variance**: Standard deviation of issues found

**Key Question**: Does confidence filtering improve precision without hurting recall too much?

## Expected Results

We expect:
- **Confidence filtering will improve precision** by 10-20 percentage points
- **Some recall loss** (maybe miss 1 of 4 real errors)
- **Lower variance** in filtered results (more consistent)
- **Severity correlation**: High severity issues will mostly be real errors
- **Confidence distribution**: Real errors will have 85-100% confidence, false positives will have 50-80% confidence

**Success criteria**: Precision > 60% while maintaining recall > 75% (3/4 real errors)

## Analysis

### Results Summary

**Key Finding**: Confidence filtering provides **modest precision improvement** (+5-17 percentage points) but **still leaves 67% false positive rate** at best.

| Strategy | Recall | Precision | F1 | Mean Issues | Notes |
|----------|--------|-----------|----|-----------|----|
| **Arrow + Line citations (conf>80%)** | **100%** | **33%** | 0.50 | 5.5 | ✅ Best overall - found all 4 real errors |
| Arrow + Structured (conf>80%) | 75% | 33% | 0.46 | 2.2 | Missed line 73 |
| Arrow + Line citations | 100% | 29% | 0.44 | 4.4 | Baseline (no filtering) |
| Arrow + Structured | 100% | 17% | 0.29 | 7.0 | High false positive rate |
| Plain text + Line citations (conf>80%) | 50% | 8% | 0.13 | 4.2 | ⚠️ Plain text fails |
| Plain text + Structured (conf>80%) | 25% | 8% | 0.12 | 2.3 | Very poor |
| Plain text + Structured | 25% | 3% | 0.06 | 6.2 | Worst |
| Plain text + Line citations | 25% | 3% | 0.05 | 6.8 | Catastrophic |

**Winner**: Line-numbered (arrow) + Line citations + Confidence filtering (>80%)
- ✅ 100% recall - Found ALL 4 real errors (lines 74, 73, 53, 32)
- ⚠️ 33% precision - Only 1/3 of flagged issues are real errors
- ⚠️ 67% false positive rate - 2/3 of flagged issues are false positives

**Improvement from confidence filtering**:
- Arrow + Line citations: 29% → 33% precision (+4 percentage points, +14% relative)
- Arrow + Structured: 17% → 33% precision (+16 percentage points, +94% relative)

**Plain text strategies failed**:
- Never found lines 73 or 74 (the H_i→H_n typos)
- High confidence (95%) but on WRONG line numbers
- Without line numbers in input, LLM cannot accurately locate errors

### Confidence/Severity Distribution

**Critical Finding**: Real errors have **highly variable confidence scores** (60-95%), making threshold-based filtering unreliable.

**Confidence scores for known real errors** (across all trials that found them):

1. **Line 74** (`H_i(i+1)` → `H_n(i+1)` typo):
   - Confidence range: 70-95%
   - Average: ~86%
   - ⚠️ Some trials scored this at only 70% (would be filtered at >75% threshold)

2. **Line 53** (math notation `2^{2^(n-1)}` → `2^{2(n-1)}`):
   - Confidence range: 60-95%
   - Average: ~84%
   - ⚠️ Some trials scored this at 60% (would be filtered at >70% threshold)

3. **Line 32** ("ending on the right to the right"):
   - Confidence range: 70-95%
   - Average: ~88%
   - Most consistent real error

4. **Line 73** (`H_i` → `H_n` in formula):
   - Only appeared in 2 trials with confidence filtering!
   - Scored exactly 80% when it appeared
   - ⚠️ At the threshold boundary - would be excluded at >80%

**False positives ALSO scored 80-95%**:
- Line 1 (LaTeX meta-commentary): 85-95% confidence
- Lines 49-52 (LaTeX semicolons): 80-90% confidence
- LLM is confident about its mistakes!

**Severity ratings were not useful**:
- Both real errors and false positives were marked "high" or "medium"
- No clear separation between error types
- Severity appears to be redundant with confidence

### Precision Improvement

Confidence filtering (>80%) improved precision modestly:

| Strategy | Baseline Precision | Filtered Precision | Improvement |
|----------|-------------------|-------------------|-------------|
| Arrow + Line citations | 29% | 33% | **+4 pp** (+14% relative) |
| Arrow + Structured | 17% | 33% | **+16 pp** (+94% relative) |
| Plain text + Line citations | 3% | 8% | +5 pp (still terrible) |
| Plain text + Structured | 3% | 8% | +5 pp (still terrible) |

**Why improvement is limited**:
1. Real errors themselves score 60-95% confidence (high variance)
2. False positives also score 80-95% confidence (overlap!)
3. Threshold of 80% is arbitrary - no natural separation point

**Trade-off analysis**:
- **Benefit**: Reduced false positives from 10-14 to 6-12 (30-40% reduction)
- **Cost**: Risk of filtering real errors (Line 73 at exactly 80%)
- **Net effect**: Precision improved from 29% to 33% (still unacceptably low)

### Recall Impact

Confidence filtering (>80%) maintained high recall for arrow strategies but catastrophically hurt plain text:

| Strategy | Baseline Recall | Filtered Recall | Real Errors Found |
|----------|----------------|-----------------|-------------------|
| Arrow + Line citations | 100% | **100%** | ✅ All 4: {74, 73, 53, 32} |
| Arrow + Structured | 100% | **75%** | ⚠️ Missed line 73 |
| Plain text + Line citations | 25% | **50%** | Only {53, 32} |
| Plain text + Structured | 25% | **25%** | Only {32} |

**Why Arrow + Structured missed Line 73**:
- Line 73 error (`H_i` in formula) appeared infrequently
- When it did appear, it scored exactly 80% confidence
- Filtering at >80% excludes it (threshold boundary effect)

**Why plain text strategies failed**:
- Without line numbers in input, LLM guesses wrong locations
- Example: Found "H_i typo" but reported it at line 45 instead of 74 (confidence: 95%!)
- High confidence on wrong line numbers = useless output

### Recommended Threshold

**Is 80% the right threshold?** No clear answer - there's no natural separation point.

**Threshold analysis**:

| Threshold | Expected Recall | Expected Precision | Trade-off |
|-----------|----------------|-------------------|-----------|
| >70% | 100% (all 4 errors) | ~25-30% | More false positives |
| >80% | 75-100% (3-4 errors) | ~30-35% | **Current choice** |
| >85% | 50-75% (2-3 errors) | ~35-40% | Miss real errors |
| >90% | 25-50% (1-2 errors) | ~40-50% | Too aggressive |

**Problem**: Real errors scored 60-95% across trials - no threshold cleanly separates them from false positives.

**Alternative approaches**:
1. **Multiple thresholds**: Show high-confidence (>90%) separately from medium (70-90%)
2. **Confidence ranges**: Report "80-95% confident" instead of binary filter
3. **Ensemble voting**: Run 3-5 trials, keep issues that appear in multiple trials
4. **Accept false positives**: 33% precision might be acceptable if user reviews manually

### Next Steps

**Conclusion**: Confidence filtering is a **modest incremental improvement** but does **not solve the fundamental precision problem**.

**What we learned**:
1. ✅ Line-numbered input is ESSENTIAL - plain text fails catastrophically
2. ✅ Confidence >80% filtering improves precision by 5-17 percentage points
3. ⚠️ Still 67% false positive rate (2 out of 3 flagged issues are wrong)
4. ⚠️ Real errors score 60-95% confidence (high variance across trials)
5. ⚠️ False positives also score 80-95% (LLM is confident about mistakes!)
6. ❌ Severity ratings are not useful (no separation between real/false)
7. ❌ No clear confidence threshold separates real from false positives

**Recommended strategy for production**:
- **Input**: Line-numbered (arrow format `N→`)
- **Output**: Line citations with confidence
- **Filtering**: Confidence >80% (weak filter, but better than nothing)
- **Expected performance**: 100% recall, 33% precision
- **User experience**: Every 3 issues, 1 is real and 2 are false positives

**Possible next experiments**:

1. **Ensemble voting** (HIGH PRIORITY)
   - Run same check 3-5 times
   - Keep only issues that appear in 2+ trials
   - Hypothesis: Real errors are more consistent across trials
   - Expected: Higher precision, similar recall

2. **Tiered confidence display**
   - Don't filter, but group by confidence: >90%, 80-90%, 70-80%
   - Let user decide which tiers to review
   - Hypothesis: User can calibrate their own threshold

3. **Multi-model consensus**
   - Run with 2-3 different models (GPT-4, Claude, etc.)
   - Keep issues flagged by multiple models
   - Hypothesis: Model agreement correlates with real errors

4. **Specialized prompts**
   - "Focus ONLY on mathematical notation inconsistencies"
   - "Focus ONLY on typos and spelling, ignore style"
   - Hypothesis: Narrower scope reduces false positives

5. **Accept current performance**
   - 33% precision might be acceptable for manual review
   - Build UI that makes reviewing 3x issues fast
   - Focus on UX: easy navigation, quick dismiss, etc.

**Recommendation**: Try **Ensemble voting** (Experiment 3) before giving up on precision improvements. If that fails, accept 30-35% precision and focus on UX.
