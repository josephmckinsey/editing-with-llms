# FAQ

## What types of checks are available?

- **`typo`** - Spelling, grammar, and typo detection. Uses Config 106 for 95% precision with Gemini 2.5 Pro.
- **`clarity`** - Identifies unclear or confusing sentences.
- **`reader`** - Checks if text is accessible to a specific reader (e.g., "a beginner programmer"). Requires `reader` field in profile.
- **`value`** - Assesses whether text provides value to the target reader. Requires `reader` field.
- **`function`** - Checks if text accomplishes its intended function (inform, convince, entertain). Requires `reader` and `function` fields.
- **`guess-function`** - Infers the text's intended purpose.
- **`guess-value`** - Infers the main value or benefit for readers.
- **`guess-reader`** - Infers the intended audience.

Example profile using `reader`:
```yaml
profiles:
  beginner-check:
    reader: "a beginner Python programmer"
    checks: [reader, clarity, value]
    model: openrouter/anthropic/claude-3.5-sonnet
```

## How do I stream the output to stdout?

By default, the tool outputs to stdout in compiler format. If you want streaming output (live LLM response):

```bash
writing-buddy quick-spell --output-format streaming document.md
```

Or create a profile with streaming:

```yaml
# .editing-config.yaml
profiles:
  stream-spell:
    checks: [typo]
    model: openrouter/google/gemini-2.5-pro-preview
    output_format: streaming
```

Then run:
```bash
writing-buddy stream-spell document.md
```

**Note:** Streaming format also writes to `output.txt` and doesn't support multiple checks.

## What options are available?

```
writing-buddy [OPTIONS] PROFILE INPUT_FILE
```

### Required Arguments
- `PROFILE` - Name of profile from `.editing-config.yaml` (e.g., `quick-spell`)
- `INPUT_FILE` - Path to file to check

### Options

**`--list-profiles`**
List all available profiles and exit.
```bash
writing-buddy --list-profiles
```

**`--dry-run`**
Print the system and user prompts without calling the LLM. Useful for debugging prompts.
```bash
writing-buddy quick-spell --dry-run document.md
```

**`--model TEXT`**
Override the model specified in the profile.
```bash
writing-buddy quick-spell --model gpt-4o document.md
```

**`--output-format [compiler|streaming|json]`**
Override the output format.
- `compiler` - Editor-friendly format: `file.md:15:1: typo: message` (default)
- `streaming` - Live LLM response, writes to output.txt
- `json` - Structured JSON output

```bash
writing-buddy quick-spell --output-format json document.md
```

**`--no-scope-restriction`**
Disable scope restriction (switches from Config 106 to Config 98). Finds more errors but with slightly lower precision (95% → 85%).
```bash
writing-buddy quick-spell --no-scope-restriction document.md
```

**`--config PATH`**
Specify a custom config file location instead of searching for `.editing-config.yaml`.
```bash
writing-buddy --config ~/my-config.yaml quick-spell document.md
```

**`--char-limit INT`**
Set character limit before warning (default: 50000). Prompts for confirmation if file exceeds limit.
```bash
writing-buddy quick-spell --char-limit 100000 large-file.md
```

## Common Examples

**Basic spell check:**
```bash
writing-buddy quick-spell document.md
```

**Check for a specific reader:**
```bash
writing-buddy bachelors-reader document.md
```

**Test prompts without API calls:**
```bash
writing-buddy quick-spell --dry-run document.md
```

**Use cheaper model for testing:**
```bash
writing-buddy quick-spell --model gpt-4o-mini document.md
```

**Get JSON output for scripting:**
```bash
writing-buddy quick-spell --output-format json document.md > results.json
```

**Broader checking (Config 98):**
```bash
writing-buddy quick-spell --no-scope-restriction document.md
```

## How do I create a custom profile?

Create or edit `.editing-config.yaml` in your project directory:

```yaml
profiles:
  my-profile:
    checks: [typo]
    model: openrouter/google/gemini-2.5-pro-preview
    custom_instructions: |
      Ignore LaTeX commands.
      The term "monad" is intentional jargon.
```

Then use it:
```bash
writing-buddy my-profile document.md
```

## What models can I use?

Any model supported by the [llm](https://github.com/simonw/llm) library. Common choices:

**For typo checking (needs Config 106):**
- `openrouter/google/gemini-2.5-pro-preview` (95% precision, recommended)
- `gpt-4o`
- `claude-3.5-sonnet`

**For reader/clarity/value checks:**
- `openrouter/anthropic/claude-3.5-sonnet` (better at perspective-taking)
- `gpt-4o`

**For cost-effective testing:**
- `gpt-4o-mini`
- `openrouter/google/gemini-2.5-flash` (but lower precision for typo checking)

## Can I run multiple checks at once?

Yes! Profiles can specify multiple checks. They run serially and combine the output:

```yaml
profiles:
  comprehensive:
    checks: [typo, clarity, reader]
    reader: "a general audience"
    model: openrouter/google/gemini-2.5-pro-preview
```

```bash
writing-buddy comprehensive document.md
```

Output shows all issues from all checks combined.

**Note:** Multiple checks are not supported with `--output-format streaming`.
