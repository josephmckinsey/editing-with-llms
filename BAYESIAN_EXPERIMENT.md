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
- Thinking: $u_{s_r}$ Do we allow reasoning tokens?

This means $u_s = u_{s_i} + u_{s_o} + u_{s_d} + u_{s_s} + u_{s_c} + u_{s_a} + u_{s_r}$, and there are $2^7 = 128$
different possible prompts. If we started with $10$ samples each, we would need $1280$ LLM calls to start with, which is around $4$. For this reason, we will start with $100$ random samples across all combinations. Then we will go through each combination of $s$ and find the one with the least certain $P(PREC_s > 0.8)$ and then collect $10$ samples from that $s$. We will repeat until $500$ maximum samples.

## Expected Results

I expect from some previous testing that none will reliably hit 75% precision and 75% recall consistently.

## Results and Analysis

No model manages to have a predicted precision of > 80%. The highest precision targets resulted in a
median of 0 errors found, which is incorrect. After looking for values that have both high precision and
high trade-off, the best options were models 29, 106, and 98 corresponding to the following configs:

```python
>>> get_config(106)
PromptConfig(use_arrow_format=False, use_structured_output=True, avoid_style=False, scope_restriction=True, use_confidence=False, prioritize_precision=True, use_reasoning=True)
>>> get_config(98)
PromptConfig(use_arrow_format=False, use_structured_output=True, avoid_style=False, scope_restriction=False, use_confidence=False, prioritize_precision=True, use_reasoning=True)
>>> get_config(29)
PromptConfig(use_arrow_format=True, use_structured_output=False, avoid_style=True, scope_restriction=True, use_confidence=True, prioritize_precision=False, use_reasoning=False)
```

Follow-up analysis with Gemini 2.5 Flash _and_ Gemini 2.5 Pro revealed the following:

```bash
Config 29: Best precision (conservative)
----------------------------------------------------------------------
  Gemini 2.5 Flash    : P=0.150, R=0.025, F1=0.043
  Gemini 2.5 Pro      : P=0.100, R=0.037, F1=0.055

Config 98: Best F1 - structured + reasoning
----------------------------------------------------------------------
  Gemini 2.5 Flash    : P=0.525, R=0.469, F1=0.495
  Gemini 2.5 Pro      : P=0.856, R=0.469, F1=0.606

Config 106: Best F1 - structured + scope + reasoning
----------------------------------------------------------------------
  Gemini 2.5 Flash    : P=0.633, R=0.362, F1=0.461
  Gemini 2.5 Pro      : P=0.951, R=0.400, F1=0.563
```

This suggests that using config 106 was much better. I also would note that config 29 might have had
parsing issues, because it spent a lot of tokens on thinking and then said no errors. In conclusion,
the final output suggests that we should use
- No line number arrows, use plain text only.
- Structured output instead of inline citations like [mistgke].
- Reporting confidence is counter productive and produces lower precision regardless.
- Reasoning tokens improve precision and probably recall too.
- Describing that the model should prioritize precision is helpful. 
- Asking to restrict its answers to a specific scope produces better precision at a marginal cost to scope.

I think that having the scope restriction on by default would be best here.

Crucially, no configuration of Gemini 2.5 Flash seems to be sufficient to do these sort of basic typo checking operations on mathematical text, and even a conservative approach does not lead to good precision.

## Implementation Details

We solve the hierarchical Bayesian model using `PyMC` and make iterative calls using Simon Willison's `llm`.

## Follow-up on the Model Type

Since the probability of detecting an error $logit(p_{l, s}) = \alpha + u_l + \sum_j u_{s, j}$,
the individual group level parameters were fitted to a general level of "eagerness" to answering. This
means that we were really only toggling one level, which was very unfortunate in retrospect.

Instead, I would do things in one of two ways:
1. We could partition the $u_{s, j}$ into $u_{s, j, FalsePositive}$ and $u_{s, j, TruePositive}$ which
would then let us separately estimate the influence each facet has on true and false positives.
2. We could add a separate effect for "Type 1" error part, so $u_{s, j} + (2 \{l \in TruePositive\} - 1) u_{s, j, l}$.

In either case, it increases the dimensionality of the number of parameters we wish to estimate.

We can also view this via the following formula instead:
$E = Eagerness = \sum_j U_{s, j}$, $I = Intelligence = \sum_j U'_{s, j}$ imply
$p_{l, s} = \alpha + u_l + E + I$ if $l$ is this is the correct answer and
$p_{l, s} = \alpha + u_l + E - I$ if this is an incorrect answer. I'd expect that most
system prompts have a larger effect on $E$ than $I$, and that choosing a bigger model mainly
impacts $I$ and not $E$.

In general, we could come up with various different factors which we try and analyze this way,
instead of just 1 or 2.

## Alternative Methodologies

Although we spent most of the effort here on calibrating precision and recall through Bayesian
methods, we only get a small number of binary variables from each method call. Ideally, each
call to the LLM should provide the maximum amount of information possible. I can think of a couple
options here:
1. Post-testing Survey

After we test an LLM with a given prompt, we could also give it the true answers, then we can ask it
what information would help it improve in the future. This could be taken from our config options,
along with an optional write-in that we could analyze later.

2. We could straight-up ask what option they would prefer best.

Both options here could actually help us as well. I'd expect there to be a correlation
between its actual task performance and the survey results, with some fixed errors
for each config option. We could try estimating those errors while figuring out what the correlation is.

Recall that in Bayesian methods, if you have more information with good assumptions, that
cannot decrease the performance of your final estimator. More information, however uncorrelated,
about things you want to estimate helps you.
