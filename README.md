# llm_typo_checker

Warning: A lot of this was written with AI. You have been warned.

A command-line tool for analyzing and editing text files using large language models (LLMs). It provides several types of checks, including typo/grammar detection, clarity analysis, reader accessibility, value assessment, and function evaluation, all powered by the [llm](https://github.com/simonw/llm) Python library.

## Features
- **Typo/Grammar Check**: Detects typos, spelling mistakes, and grammatical errors.
- **Clarity Check**: Identifies unclear or confusing sentences.
- **Reader Accessibility**: Estimates whether a described reader will struggle to understand the text.
- **Value Assessment**: Checks if the text provides value to a specific reader.
- **Function Evaluation**: Assesses whether the text accomplishes its intended function (e.g., inform, convince, entertain).
- **Guessing Tools**: Infers the likely function, value, or intended reader of a text.

## Installation
1. Clone this repository:
   ```sh
   git clone https://github.com/josephmckinsey/editing-with-llms
   cd editing-with-llms
   ```
2. Install dependencies:
   ```sh
   pip install llm click
   ```

## Usage
Run the tool from the command line:

```sh
python llm_typo_checker.py [OPTIONS] INPUT_FILE
```

### Options
- `--check [typo|clarity|reader|value|function|guess-function|guess-value|guess-reader]`  
  Type of check to perform (default: `typo`).
- `--model MODEL`  
  Model name or alias to use with llm (optional).
- `--reader READER`  
  Describe the intended reader for the 'reader', 'value', or 'function' check. Should complete the clause "from the perspective of..."
- `--function FUNCTION`  
  Describe the intended function for the 'function' check (e.g., inform, convince, entertain). Should complete the clause "{function} {reader}" or "{function} a general reader".

### Example
Check a file for typos:
```sh
python llm_typo_checker.py --check typo my_article.txt
```

Check for clarity issues:
```sh
python llm_typo_checker.py --check clarity my_article.txt
```

Assess accessibility for a beginner:
```sh
python llm_typo_checker.py --check reader --reader "a beginner Python programmer" my_article.txt
```

## Output
Results are printed to the console and also written to `output.txt` in the current directory.

## License
MIT License
