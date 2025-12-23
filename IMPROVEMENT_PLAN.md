# Implementation Plan for editing-with-llms

This is a focused, actionable plan based on user feedback and priorities.

## Core Philosophy
- Point out errors and problems, rarely if ever make suggestions
- Let the writer's voice come through
- Focus on reader perspective and value

---

## Phase 0: Testing & Prototyping (DO THIS FIRST)

Before committing to an architecture, test different approaches:

### Input Format Strategies
Test how to send text to LLM:
1. **Line-numbered input**: Prepend `N→` to each line (like Claude Code's Read tool)
2. **Structured markers**: Use XML-style tags for sections
3. **Plain text with post-processing**: Send plain text, try to match LLM output back to source

### Output Parsing Strategies
Test how to get consistent location data:
1. **Request line citations**: Ask LLM to cite "Line N: [text]"
2. **Structured output format**: Request specific format like "LINE: N\nTEXT: ...\nISSUE: ..."
3. **JSON output**: Use prompt engineering to get JSON responses
4. **Fuzzy text matching**: LLM returns text fragments, we match them to original

### Format Handling Test
Test with actual documents (Markdown, LaTeX, Typst, Lean 4):
1. **Prompt engineering only**: Instruct LLM to ignore code/commands
2. **Pre-processing**: Strip code blocks/commands before sending
3. **Hybrid**: Keep structure but mark ignorable sections

**Deliverable:** Create `test_strategies.py` that runs same document through different strategies and compare results.

---

## Phase 1: Foundation (High Impact, Low Effort)

### 1.1 Named Profile Configs
Implement `.editing-config.yaml`:
```yaml
quick-spell:
  checks: [spelling-basic, grammar-basic]

spell:
  checks: [spelling-llm, grammar-llm]
  model: gpt-4o-mini

bachelors-reader:
  reader: "a Bachelor's in mathematics who mostly knows what formal verification is"
  checks: [reader, clarity, value]
  model: gpt-4o
```

Usage: `python llm_typo_checker.py bachelors-reader test.md`

### 1.2 Compiler-Style Output
Basic output format:
```
test.md:15:23: clarity: This sentence uses nested clauses that obscure the main point.
test.md:42:1: reader: This paragraph assumes knowledge of monads.
```

### 1.3 Line Number References
Based on Phase 0 testing results:
- Implement chosen input format strategy
- Implement chosen output parsing strategy
- Create data model for issues

---

## Phase 2: Proper Package Structure (High Impact, Medium Effort)

### 2.1 Move to pyproject.toml
Set up modern Python package:
- Use `uv` or standard `pyproject.toml`
- Define dependencies: `click`, `llm`, `proselint`, `language-tool-python`, etc.
- Proper package structure
- Entry point for CLI

### 2.2 Modular Architecture
```
editing-with-llms/
  src/
    editing_llms/
      __init__.py
      cli.py              # Click CLI
      config.py           # Load .editing-config.yaml
      checks/
        __init__.py
        base.py           # Base check interface
        llm_checks.py     # Typo, clarity, reader, value, function
        local_checks.py   # proselint, language-tool integration
      output/
        __init__.py
        models.py         # Issue dataclass
        compiler.py       # Compiler-style formatter
        terminal.py       # Terminal diff-style with colors
      formats/
        __init__.py
        markdown.py
        latex.py
        typst.py
  tests/
  pyproject.toml
```

### 2.3 Terminal Diff-Style Output with Color
```
test.md:15-17
  14 | The team met to discuss the project.
  15 | The process was completed, but the results,
> 16 | which were unexpected, led to further questions
       ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  17 | about the initial assumptions.
  18 | Everyone agreed to meet again.

clarity: This sentence has multiple nested clauses that obscure the main point.
```

Use libraries like `rich` or `colorama` for terminal colors.

---

## Phase 3: Hybrid Checking (High Impact, Medium Effort)

### 3.1 Integrate Local Tools
Add fast, free checks:
- `proselint`: Style and usage issues
- `language-tool-python`: Grammar checking
- `pyspellchecker` or `aspell`: Spelling

### 3.2 Format-Aware Preprocessing
Based on Phase 0 testing, implement:
- Document format detection (by extension or config)
- Format-specific preprocessing (if needed)
- Custom ignore patterns per format

### 3.3 Check Profiles
In `.editing-config.yaml`:
```yaml
quick-spell:
  checks:
    - spelling-basic    # uses pyspellchecker
    - grammar-basic     # uses language-tool
    - style-basic       # uses proselint

deep-spell:
  checks:
    - spelling-llm      # LLM-based
    - grammar-llm
  model: gpt-4o-mini
```

---

## Phase 4: Shared Data Model (High Impact, High Effort)

### 4.1 Unified Issue Representation
```python
@dataclass
class Issue:
    file: Path
    line_start: int
    line_end: int
    col_start: Optional[int]
    col_end: Optional[int]
    text: str              # The problematic text
    issue_type: str        # "clarity", "reader", "typo", etc.
    explanation: str
    severity: str          # "critical", "medium", "minor"
    check_source: str      # "llm-gpt4", "proselint", "languagetool"
```

### 4.2 Multiple Output Formats
All formats use same Issue model:
- Compiler-style (for editors/scripts)
- Terminal diff-style (for humans)
- JSON (for tools)
- LSP format (future: editor integration)

---

## Future / Deferred

Keep in mind but don't implement yet:

### Document Chunking & Summarization
- For very long documents
- Document map generation
- Contextual checking with summaries

### Interactive Modes
- TUI for navigating issues
- Watch mode for live checking
- REPL mode

### Editor Integration
- VS Code extension
- LSP server

### Batch & Workflow
- Batch processing
- CI/CD integration
- Comparison mode

### Enhanced Checks
- Only add new check types after reading more writing books
- Focus on reader value, not arbitrary rules

---

## Open Questions to Resolve

### 1. proselint + LaTeX/Special Symbols
**Problem:** proselint will complain about LaTeX commands like `\textbf`, math symbols, etc.

**Testing Results (on Lean documentation file):**

**proselint:**
- ✅ Found legitimate style issues: curly quotes, weasel words ("very"), clichés
- ❌ False positives in code blocks: "omega omega", "simp simp" flagged as lexical illusions
- ❌ Complained about `...` in code examples (wants ellipsis symbol `…`)
- **Overall:** Decent for prose, but needs code block filtering

**pyspellchecker:**
- ❌ Massive false positives: LaTeX (`$\latex$`, `\times`), Markdown (`##`, `::::blob`)
- ❌ Flags technical terms: `mathlib`, `hilbert`, ordinals like `0th`
- **Overall:** Unusable without heavy preprocessing

**language-tool-python:**
- ❌ False positives on Lean syntax: `=>` flagged as needing arrow symbol
- ❌ Spelling errors on technical terms: `hilbert`, `invertibility`, `ProofWidgets`, `mathlib`
- ✅ Would likely find real grammar issues in prose
- **Overall:** Needs preprocessing to strip code/LaTeX

**Recommendation:**
1. **For Markdown:** Use proselint on prose sections only (skip code blocks)
2. **For LaTeX/Lean:** Skip local tools entirely, rely on LLM checks
   - LLMs understand "ignore LaTeX commands" in prompts
   - Can differentiate between prose and code context
3. **Format detection:** Use file extension or config to choose strategy
4. **Future:** Implement format-specific preprocessing if LLM-only approach is too slow/expensive

### 2. Custom Instructions per Document
Should `.editing-config.yaml` support custom instructions?
```yaml
bachelors-reader:
  reader: "..."
  custom_instructions: |
    Ignore mathematical notation in $...$ blocks.
    The term "morphism" is intentional jargon.
  ignore_patterns:
    - '\$.*?\$'
    - '\\cite\{.*?\}'
```

### 3. Model Selection Strategy
- Default model for each check type?
- Cheap model for first pass, expensive for review?
- Per-profile model configuration?

---

## Success Metrics

After Phase 1-3, we should have:
- [ ] Named profiles in config file
- [ ] Fast local checks + LLM checks working together
- [ ] Clear, actionable output with precise locations
- [ ] Works correctly with LaTeX/Markdown/Typst/Lean documents
- [ ] Proper package that can be installed with `pip install -e .`
- [ ] Maintained focus on reader perspective, not prescriptive rules
