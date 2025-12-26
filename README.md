# writing-buddy

Warning: A lot of this was written with AI. You have been warned.

A command-line tool for analyzing and editing text files using large language models (LLMs). It provides several types of checks, including typo/grammar detection, clarity analysis, reader accessibility, value assessment, and function evaluation, all powered by the [llm](https://github.com/simonw/llm) Python library.

This scaffolding is intended to be used _after_ writing, preferably after a first or second draft, but before you
send it to a friend or human editor.

When used with `openrouter/anthropic/claude-sonnet-4.5`, typo checking 600 lines (9000 tokens) costs around $0.05 to $0.15 per check. I've tended to need at least 5 runs to get most typos.

## Baked-in Prompts

None of these prompts are instructed to make suggestions; ignore any suggestions that the LLM sneaks
through. You can see the exact system and user prompt with "

- **`typo`** - Spelling, grammar, and typo detection.
- **`clarity`** - Identifies unclear or confusing sentences.
- **`reader`** - Checks if text is accessible to a specific reader (e.g., "a beginner programmer"). Requires `reader` field in profile.
- **`value`** - Assesses whether text provides value to the target reader. Requires `reader` field.
- **`function`** - Checks if text accomplishes its intended function (inform, convince, entertain). Requires `reader` and `function` fields.
- **`guess-function`** - Infers the text's intended purpose.
- **`guess-value`** - Infers the main value or benefit for readers.
- **`guess-reader`** - Infers the intended audience.

## Installation
1. Clone this repository:
   ```sh
   git clone https://github.com/josephmckinsey/editing-with-llms
   cd editing-with-llms
   ```
2. Install:
   ```sh
   pip install .
   ```

## Alternatively with uv

- `uv tool install /path/to/package --with llm-openrouter`
- `uvx --from editing-with-llms writing-buddy ...`

## Usage

1. Make an `.editing-config.yaml` like in the repository:

```yaml
profiles:
  quick-spell:
    checks: [typo]
    # Specify the model with name from `llm models list`.
    model: openrouter/google/gemini-2.5-pro-preview

  normal-reader:
    reader: "a Bachelor's in mathematics who mostly knows what formal verification is"
    checks: [reader, clarity, value]
    model: openrouter/anthropic/claude-sonnet-4.5

  math-doc:
    checks: [typo]
    model: openrouter/google/gemini-2.5-pro-preview
    prompt_config:
      scope_restriction: false  # Broader check
    custom_instructions: |
      Ignore LaTeX commands like \textbf, \cite, etc.
      The terms "morphism", "functor", and "category" are intentional jargon.
      Do not flag mathematical notation in $...$ blocks.

  # Streaming output for these modes
  guess-audience:
    checks: [guess-reader, guess-function, guess-value]
    model: gpt-4o-mini
    output_format: streaming
```

It is recommended that you use a powerful enough reasoning model. I've found that even low or medium reasoning
improves the precision and recall dramatically.

I also recommend thinking quite hard about what readers and functions your work is supposed to serve.

2. Run the tool from the command line:

```sh
writing-buddy [OPTIONS] INPUT_FILE
```

### Options

- `--config PATH`: Path to config file (default: search for .editing-config.yaml)
- `--model TEXT`: Override profile model
- `--output-format [compiler|streaming|json]`: Override output format
- `--no-scope-restriction`: Disable scope restriction
- `--list-profiles`: List available profiles and exit
- `--dry-run`: Print prompts without calling LLM
- `--char-limit INTEGER`: Warn if input exceeds this many characters (default: 50000)
- `--help`: Show this message and exit.

## TODO Improvements

- Being able to reuse an LLM may allow you to have lower costs. For instance, you may
ask for typos, get 10 errors, then you say "fixed", and it gives another 10. This can save
on costs. Just being able to drop into "chat" mode is helpful often.
- Simliarly, being able to combine multiple checks may be helpful in many instances,
although I expect that to reduce performance.

## License
MIT License
