# CLAUDE.md - Developer Context for editing-with-llms

## Project Overview
A CLI-based text editing tool that uses LLMs to bridge the author-reader gap. The core insight is that most editing problems arise from the difference between the author's and reader's perspectives, and LLMs can simulate reader perspectives to identify issues.

- Focus on the reader's perspective especially the value provided to a reader
- LLMs uniquely positioned to simulate reader perspectives
- Point out errors and problems but rarely if ever make suggestions

## Current Architecture

### Core Components
- **llm_typo_checker.py**: Main CLI tool built with Click
- **llm library**: Uses Simon Willison's llm Python library for LLM access
- **OpenRouter**: User typically uses OpenRouter for cost-effective testing before using expensive models

### Check Types
1. **typo**: Spelling and grammar errors
2. **clarity**: Unclear or confusing sentences
3. **reader**: Accessibility for a specific reader profile
4. **value**: Whether text provides value to the target reader
5. **function**: Whether text accomplishes its intended function (inform, convince, etc.)
6. **guess-function**: Infers the text's intended function
7. **guess-value**: Infers the main value for readers
8. **guess-reader**: Infers the intended audience

### Current Workflow
```bash
python llm_typo_checker.py --check reader \
  --reader "a Bachelor's in mathematics who mostly knows what formal verification is" \
  test
```

Output goes to both console (streaming) and `output.txt`

## Known Limitations & User Concerns

### Configuration Issues
- Reader definitions must be typed every time (tedious for repeated checks)
- No per-document configuration storage
- No way to save common reader profiles

### Output Management
- It's difficult to find where the suggestions point to.

### Scalability Issues
- No chunking strategy for long documents
- No summarization for out-of-context information

### Interaction Model
- Currently one-shot CLI tool
- Could benefit from interactivity (like Claude Code or VS Code extension)

### Alternative Libraries
- User wonders if specialized spell-check/grammar libraries might be better for basic checks
- Trade-off: speed/cost vs. consistency with LLM-based checks

## Development Context
- Python 3.13
- Dependencies: click, llm
- Has test suite (test_llm_typo_checker.py)
- Uses venv for environment management
- Git-tracked, MIT licensed

## Future Directions (User's Ideas)
See brainstorming in main conversation for detailed improvement proposals.
