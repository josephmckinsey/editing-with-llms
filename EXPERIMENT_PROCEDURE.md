# Experiment Title

We are attempting to test whether and how current LLMs can be used for spellcheck, grammar,
and typo checking in complicated environments like Lean 4's markdown variant. This task
is highly challenging.

## Setup

We will be checking against a document called `test` which is one of my Lean 4 blog posts on Hilbert
curves. There are a few errors within the first 100 lines, but generally it is around what I want.

From this, we must first go through the text very carefully to determine all _true_ errors.
We may also want to categorize "false" errors as well, but that is not necessary. We may also
want to categorize the _true_ errors in order of helpfulness.

Using Gemini 2.5 Flash, we will run the text under several different system prompts, parse the output,
and then find how many errors there are. We can vary the following characteristics
- input format (plain text, line numbers annotated with arrows)
- output format (line citations, structured output)
- additional direction to prevent common failure modes
- confidence levels and severity--allowing control over the precision-recall tradeoff.
- stronger or weaker scope restrictions (i.e. focus more on typos, grammar, etc.)
- more or less information on precision-recall testing? i.e. "aim for 80% of your results being helpful in the worst case, expect users to rerun if there are more problems"

## Hypothesis

The hypothesis is that Gemini 2.5 Flash is incapable of consistently giving precise, helpful feedback. Specfically, the null hypothesis is that >75% precision and >75% recall is impossible.

## Methods

LLM output tends to be highly variable. Under ordinary temperature testing, which should approximate testing under a more diverse document set, they can output as few as 0 issues or as many as 24 issues for one given call. In samples of size 10, some runs would work well and others would work poorly.

We will model the event that the llm detects an error at location $l$ as $E(l, s)$ where $s$ is a variable depending on the prompt. The number of false positives is $\sum_{l \in False} E(l, s)$, and the number
of true positives as $\sum_{l \in True} E(l, s)$. We can assume that $p_{l,s} = P(E(l, s))$ will depend on several other effects: $logit(p_{l, s}) = \alpha + u_l + u_s$. For priors, we can assume that $\alpha \sim N(0, 5)$, $u_l \sim N(0, \sigma_{loc})$, $u_s \sim N(0, \sigma_{sys})$ where $\sigma_{loc}, \sigma_{sys} \sim Exponential(5)$. I'm not so confident about those priors yet, I need to try sampling from them and eseing if that matches my expectation as a posterior prediction check.

We will then fit a MCMC model using $E(l, s)$ across $n$ samples; we will assume that
each particular run is unmixed (so no error is attributable to a specific run). If we compute $m$
MCMC samples, then we can compute $PREC_s = \sum_{l \in Good} p_{l, s} / \sum_{l} p_{l, s}$ for 
the precision at each MCMC sample for each system $s$. We can then compute the probability that
$P(PREC_s > 0.8)$ by aggregating over all the MCMC samples.

We should incrementally do samples in size 10 and then run MCMC tests until $P(PREC_s > 0.8)$ is
either $ < 0.1$ or $> 0.9$ for each $s$. We should also prioritize prompt options on scenarios
which are less certain.

To get data from this, we will compute and extract errors from several different test cases:
- Input Format: $u_{s_i}$ plain text vs arrows with line numbers
- Output Format: $u_{s_o}$ line citation vs structured
- Additional Direction: $u_{s_d}$ the addition of the text "Avoid commenting on style".
- Scope Direction: $u_{s_s}$ "Do not report perceived errors outside of spelling, grammar, or typos."
- Confidence levels: $u_{s_c}$ the addition of confidence levels and filtering to the 80% level.
- Context: $u_{s_a}$ "Aim for more than 80% of your errors being helpful. Expect users to rerun later if they need to find new errors, so prioritize precision."

This means $u_s = u_{s_i} + u_{s_o} + u_{s_d} + u_{s_s} + u_{s_c} + u_{s_a}$, and there are $2^6 = 64$
different possible prompts. If we started with $10$ samples each, we would need $640$ LLM calls to start with, which is around $2$. For this reason, we will start with $100$ random samples across all combinations. Then we will go through each combination of $s$ and find the one with the least certain $P(PREC_s > 0.8)$ and then collect $10$ samples from that $s$. We will repeat until $500$ maximum samples.

## Expected Results

I expect from some previous testing that none will reliably hit 75% precision and 75% recall consistently.

## Results

## Analysis

## Implementation Details

We solve the hierarchical Bayesian model using `PyMC` and make iterative calls using Simon Willison's `llm`.
