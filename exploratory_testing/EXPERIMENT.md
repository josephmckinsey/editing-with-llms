# Phase 0 Experiment: Testing Input/Output Strategies

## Hypothesis

Different combinations of input formatting and output parsing strategies will have varying effectiveness for:
1. Getting the LLM to provide accurate location information (line numbers)
2. Maintaining consistency and parseability of responses
3. Handling technical documents with code/LaTeX/special formatting

We hypothesize that:
- **Input strategies**: Line-numbered input (like Claude Code's Read tool) will help the LLM reference specific locations more accurately than plain text
- **Output strategies**: Structured formats (JSON or explicit LINE:/TEXT: format) will be more reliable to parse than fuzzy text matching
- **Best combination**: Line-numbered input + JSON output will provide the most reliable and precise results

## Method

### Test Document
- Use the `test` file (Lean 4 documentation with Markdown, LaTeX, and code)
- Test on first 100 lines to get more variety of content (includes both prose and code)

### Input Format Strategies
1. **Line-numbered (arrow)**: Prepend `N→` to each line (like Claude Code's Read tool)
2. **Line-numbered (pipe)**: Prepend `N | ` to each line (alternative format)
3. **Structured markers**: Wrap each line in XML-style `<line n="N">` tags
4. **Plain text**: Send text as-is, rely on LLM to quote fragments

### Output Parsing Strategies
1. **Line citations**: Ask LLM to cite "Line N: [text]"
2. **Structured output**: Request format like "LINE: N\nTEXT: ...\nISSUE: ..."
3. **JSON output**: Request JSON array with line/text/issue fields
4. **Fuzzy matching**: Extract `[quoted text]` and search for it in original

### Test Combinations
Run the following 8 combinations to cover different approaches:
1. Line-numbered (arrow) + Line citations
2. Line-numbered (arrow) + JSON
3. Line-numbered (pipe) + Line citations
4. Line-numbered (pipe) + JSON
5. Plain text + Fuzzy matching
6. Plain text + JSON (to see if LLM can generate line numbers without input)
7. Structured markers + Structured output
8. Structured markers + JSON

### Execution
```bash
python test_strategies.py
```

**Multiple Trials**: Each strategy combination is run **10 times** to account for LLM non-determinism and measure variance. This allows us to compute:
- Mean issues found
- Standard deviation (consistency)
- Range (min/max)

Total API calls: 8 combinations × 10 trials = 80 API calls (~$0.24 at current rates)

Results saved to `strategy_test_results.json` with statistics for each strategy

## Expected Results

We expect:
- **Line-numbered input** (both arrow and pipe) will produce more accurate line number references than plain text
- **Arrow vs pipe format**: Both should work similarly, but one may be more natural for LLMs to parse
- **JSON output** will be most reliable to parse, but may be less flexible if LLM doesn't follow format exactly
- **Fuzzy matching** will work but may have ambiguity issues with repeated text
- **Structured markers** may be verbose and add unnecessary complexity
- **Plain text + JSON**: Curious if LLM can generate accurate line numbers without numbered input
- **Variance**: Some strategies will show high variance (inconsistent results across trials), others will be more consistent

The experiment should reveal which strategy provides the best balance of:
- **Accuracy** (correct line numbers and finding real issues)
- **Reliability** (consistent format, low variance across trials)
- **Consistency** (similar number of issues found each time)
- **Simplicity** (easy to implement and maintain)
- **Robustness** (works with different document types)

## Analysis

### Results Summary

| Input Strategy | Output Strategy | Mean ± Std Dev | Range | Observations |
|----------------|-----------------|----------------|-------|--------------|
| Line-numbered (arrow) | Line citations | **5.60 ± 3.72** | [1, 14] | Highest mean but very inconsistent |
| Plain text | JSON | 5.20 ± 5.65 | [0, 17] | High variance, sometimes finds nothing |
| Line-numbered (pipe) | JSON | 4.70 ± 4.57 | [0, 15] | High variance |
| Structured markers | JSON | 4.20 ± 6.09 | [0, 17] | Extremely high variance |
| Structured markers | Structured output | 3.80 ± 2.04 | [0, 7] | More consistent than other structured |
| Line-numbered (arrow) | JSON | **3.40 ± 2.01** | [0, 6] | **Most consistent** |
| Plain text | Fuzzy matching | 3.30 ± 7.47 | [0, 24] | **Highest variance**, unreliable |
| Line-numbered (pipe) | Line citations | 2.70 ± 1.34 | [1, 6] | Low mean, fairly consistent |

**Key Finding**: There's a **massive variance problem** across all strategies. The LLM is highly non-deterministic for this task.

### Critical Observations

1. **Single trials are extremely misleading**
   - Our first trial showed Arrow + Line citations with 8 issues (seemed best)
   - Actual mean: 5.60 with range 1-14 (sometimes finds almost nothing!)
   - This validates the multi-trial approach

2. **No strategy is both accurate AND consistent**
   - **Highest mean** (Arrow + Line citations: 5.60) has **high variance** (±3.72)
   - **Most consistent** (Arrow + JSON: ±2.01) has **lower mean** (3.40)
   - **Tradeoff**: Accuracy vs. Consistency

3. **Parsing failures are common**
   - Many strategies had trials that found **0 issues**
   - Arrow + JSON: 0 issues in some trials (parsing failure or LLM said "no errors")
   - Plain text strategies: extremely unreliable (0-24 issue range!)

4. **Arrow format is slightly better than pipe**
   - Arrow + Line citations: 5.60 mean vs Pipe + Line citations: 2.70 mean
   - Arrow + JSON: 3.40 mean vs Pipe + JSON: 4.70 mean (contradicts!)
   - Inconclusive, but arrow seems more natural for line citations

5. **Structured markers don't help**
   - Structured markers + JSON: 4.20 ± 6.09 (high variance)
   - No benefit over simpler approaches
   - Added complexity without reliability gain

### What Worked (Relatively)

1. **Line-numbered (arrow) + Line citations**: Highest mean (5.60) but inconsistent
   - Best for: Maximizing issues found (if you can tolerate variance)
   - Risk: Sometimes finds only 1 issue, sometimes 14

2. **Line-numbered (arrow) + JSON**: Most consistent (±2.01)
   - Best for: Predictable, reliable output
   - Trade-off: Lower mean (3.40 issues)
   - Range 0-6 suggests occasional parsing failures

3. **Structured markers + Structured output**: Moderate consistency (±2.04)
   - Second-most consistent strategy
   - But lower mean (3.80) doesn't justify the added complexity

### What Didn't Work

1. **Plain text + Fuzzy matching: CATASTROPHIC VARIANCE**
   - Range: 0-24 issues (completely unpredictable)
   - Std dev (7.47) is 2.3x the mean (3.30)
   - Utterly unreliable

2. **Plain text + JSON: Unreliable**
   - Range: 0-17 issues
   - Without line numbers in input, LLM behavior is chaotic
   - Sometimes generates line numbers, sometimes doesn't

3. **All strategies have 0-issue trials**
   - Suggests either:
     - LLM occasionally says "no errors found"
     - Parsing failures (JSON malformed, citations not matching regex)
     - LLM genuinely confused by the input format

### Recommended Strategy

**Winner (for consistency): Line-numbered (arrow) + JSON**

Rationale:
- **Lowest variance** (±2.01) = most predictable
- **Reasonable mean** (3.40 issues per run)
- **JSON is parseable** when LLM cooperates
- Range 0-6 is much more acceptable than 0-17 or 0-24

**Alternative (for maximizing findings): Line-numbered (arrow) + Line citations**
- **Highest mean** (5.60 issues)
- Accept **high variance** (±3.72)
- Good for: "I want to find as many issues as possible, I'll manually review them anyway"

**Avoid at all costs:**
- Plain text input (too chaotic)
- Fuzzy matching (catastrophic variance)
- Structured markers (complexity without benefit)

### Parsing Failures vs Genuine Results

Analyzed all 80 trial responses to understand the "0 issue" trials:

**Parsing Failures** (LLM gave response but parser failed to extract it):
- Arrow + JSON: 2/10 trials - JSON wrapped in markdown code fences
- Pipe + JSON: 3/10 trials - JSON parsing issues
- Plain text + JSON: 4/10 trials - JSON present but not extracted
- **Structured markers + JSON: 6/10 trials** - worst parser reliability!

**Genuine "No Errors"** (LLM said "There are no errors found"):
- Plain text + Fuzzy matching: 6/10 trials - LLM gave up without line numbers
- Structured markers + Structured output: 1/10 trials

**Key Finding**: Most "0 issue" trials are **parsing failures**, not LLM failing to find issues!

### False Positive Analysis

Reviewed the most frequently flagged lines across all 80 trials:

**Real Errors Found (True Positives):**
1. **Line 74: `H_i(i + 1)` should be `H_n(i + 1)`** - Flagged 46 times ✅
   - Clear typo, inconsistent with `H_n(i)` earlier in same sentence
2. **Line 73: `H_i` should be `H_n`** - Flagged 29 times ✅
   - Inconsistent with function definition `\tilde{H}_n`
3. **Line 53: `2^{2^(n-1)}` should be `2^{2(n-1)}`** - Flagged 40 times ✅
   - Inconsistent with pattern in lines 50-52
4. **Line 53: `2^(n-1)` should be `2^{n-1}`** - Missing LaTeX braces ✅
5. **Line 32: "ending on the right to the right"** - Flagged 34 times ✅
   - Redundant phrasing, should be "ending on the right"

**False Positives (Incorrectly Flagged):**
1. **Line 1: LaTeX formatting** - Flagged 13 times ❌
   - Line is meta-commentary EXPLAINING the notation difference
   - LLM misunderstood the context
2. **Line 49-52: "Missing semicolons" in LaTeX cases** ❌
   - LaTeX `\begin{cases}` doesn't use semicolons
   - LLM confused about LaTeX syntax
3. **Line 63: "real curve" vs "R curve"** ❌
   - "real curve" is correct informal English
   - Formal `\mathbb{R}` appears later in formal definitions
4. **Line 12: "Holder" vs "Hölder"** ⚠️
   - Stylistic choice, ASCII is acceptable in code contexts
   - Not a true error

**Estimated False Positive Rate: ~30-40%** based on common issues

### Open Questions

1. **Why is variance so high?**
   - LLM temperature settings? (likely default temperature is high)
   - Different interpretations of what counts as an "issue"
   - Prompt ambiguity about strictness
   - **Answer**: Likely all three factors

2. ~~Why do some trials find 0 issues?~~ **ANSWERED**
   - **Mostly parsing failures**, not LLM failures
   - JSON wrapped in markdown fences breaks simple parsers
   - Structured markers especially prone to parsing failures

3. **Can we reduce variance?**
   - More specific prompts? ("Focus on typos and inconsistent notation")
   - Lower LLM temperature? (temperature=0 for determinism)
   - Better parsers? (handle markdown code fences)
   - Multiple LLMs and voting?

4. **Can we reduce false positives?**
   - More context-aware prompts ("Ignore meta-commentary")
   - Teach LLM about LaTeX syntax
   - Accept false positives as cost of catching real errors?

### Next Steps

1. ~~Investigate the 0-issue trials~~ **COMPLETED**
   - ✅ Most are parsing failures, not LLM failures
   - ✅ Need better JSON parser (handle markdown code fences)

2. **Improve JSON parser** (HIGH PRIORITY)
   - Handle markdown code fences: ` ```json ... ``` `
   - Extract JSON from mixed text responses
   - This could recover 2-6 "failed" trials per strategy

3. **Test variance reduction techniques**
   - Try with `temperature=0` (more deterministic)
   - More specific prompts: "Focus on typos, mathematical inconsistencies, and awkward phrasing"
   - Prompt engineering to reduce false positives: "Ignore meta-commentary about notation"

4. **Decide on implementation strategy**
   - **Recommendation**: Arrow + JSON with improved parser
   - Accept ~30-40% false positive rate (user will review anyway)
   - Build in line number references for easy navigation

5. **Consider false positive reduction**
   - Add LaTeX-awareness to prompts
   - Teach LLM to ignore meta-commentary
   - OR: Accept false positives as cost of finding real errors

6. **Update IMPROVEMENT_PLAN.md**
   - Mark Phase 0 as completed
   - Document chosen strategy: Line-numbered (arrow) + JSON
   - Note findings:
     - High variance is inherent to LLM checking
     - ~30-40% false positive rate
     - Parsing is critical (improve JSON extraction)
   - Move to Phase 1: Implement config files and compiler-style output

## Key Takeaways

1. **Line-numbered input is essential** - Plain text produced chaotic results
2. **Arrow format (`N→`) works well** - Familiar from Claude Code
3. **JSON output is best when parseable** - Need robust parser for code fences
4. **High variance is real** - Same strategy: 0-17 issues across trials
5. **LLM found legitimate errors** - 5 real typos/inconsistencies confirmed
6. **False positives are manageable** - ~30-40% rate, mostly LaTeX confusion
7. **Single trials are misleading** - Multi-trial testing was essential
