# Implementation Plan for editing-with-llms

This is a focused, actionable plan based on user feedback and priorities.

## Status Tracking

**Completed:**
- ✅ Phase 2.1: Created pyproject.toml with modern package structure
- ✅ Phase 2.1: Migrated to src/ layout (src/editing_with_llms/)
- ✅ Phase 2.1: Entry point CLI command (`writing-buddy`)
- ✅ Phase 2.1: Moved tests to tests/ directory
- ✅ Testing: Tested proselint, pyspellchecker, language-tool-python on real docs
- ✅ Testing: Updated test suite with synonym-based assertions
- ✅ **Phase 0: Bayesian experiment testing 128 prompt combinations**
  - ✅ Tested input formats (plain text vs arrow line numbers)
  - ✅ Tested output formats (structured vs line citations)
  - ✅ Tested 7 prompt factors with hierarchical Bayesian modeling
  - ✅ Compared Gemini 2.5 Flash vs Pro performance

**In Progress:**
- 🔄 Phase 1: Config file, compiler output, line number references

**Not Started:**
- ⏳ Phase 2.2-2.3: Full modular architecture, terminal output
- ⏳ Phase 3: Hybrid checking, format-aware preprocessing

---

## Core Philosophy
- Point out errors and problems, rarely if ever make suggestions
- Let the writer's voice come through
- Focus on reader perspective and value

---

## Phase 0: Testing & Prototyping ✅ COMPLETED

**Methodology:** Ran rigorous Bayesian experiment testing 128 prompt combinations (2^7 factors) with hierarchical modeling.
See `BAYESIAN_EXPERIMENT.md` for full details.

### Results

**Best Configuration (Config 106):**
```python
PromptConfig(
    use_arrow_format=False,           # ✅ Plain text input
    use_structured_output=True,       # ✅ Structured format: TEXT/ISSUE
    avoid_style=False,
    scope_restriction=True,           # ✅ "Do not report errors outside spelling/grammar/typos"
    use_confidence=False,             # ❌ Counter-productive
    prioritize_precision=True,        # ✅ "Aim for >80% helpful, prioritize precision"
    use_reasoning=True                # ✅ Enable reasoning tokens
)
```

**Performance (Gemini 2.5 Pro):**
- **Precision: 95.1%** (only 1 in 20 flagged issues is false!)
- Recall: 40.0% (finds ~half of errors)
- F1: 0.563

**Key Findings:**
1. **Input format:** Plain text works best. Line numbers/arrows hurt performance.
2. **Output format:** Structured format (TEXT/ISSUE fields) better than line citations.
3. **Crucial factors:**
   - Reasoning tokens (+0.79 effect)
   - Structured output (+0.91 effect)
   - Prioritize precision instruction (+0.12 effect)
   - Scope restriction helps slightly
4. **Counter-productive factors:**
   - Confidence filtering (-1.08 effect) - removes too much
   - Arrow line numbers (-0.79 effect)
   - "Avoid style" direction (-0.47 effect)

**Model Selection:**
- ❌ Gemini 2.5 Flash: Max 63% precision, best is 40% recall (too conservative)
- ✅ **Gemini 2.5 Pro: Production model** (95% precision with 40% recall)

**Alternative config (Config 98)** for slightly higher recall:
- Same as 106 but without `scope_restriction`
- Precision: 85.6%, Recall: 46.9%, F1: 0.606

**Implementation Decision:**
Use Config 106 as default, with optional flag to disable scope restriction (Config 98) for broader checking.

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

Usage: `writing-buddy bachelors-reader test.md`

### 1.2 Compiler-Style Output
Basic output format:
```
test.md:15:23: clarity: This sentence uses nested clauses that obscure the main point.
test.md:42:1: reader: This paragraph assumes knowledge of monads.
```

### 1.3 Line Number References
Based on Phase 0 results:
- ✅ **Input format:** Send plain text (no line numbers)
- ✅ **Output format:** Request structured format with TEXT/ISSUE fields
- **Parsing:** LLM provides TEXT snippet, we find line number via string matching
- **Data model:** Issue with text, issue_type, explanation, line_number
- **LLM options:** Enable `reasoning_max_tokens=2000` for Gemini models

---

## Phase 2: Proper Package Structure (High Impact, Medium Effort)

### 2.1 Move to pyproject.toml ✅ COMPLETED
Modern Python package setup:
- ✅ Created pyproject.toml with dependencies
- ✅ Core deps: `click`, `llm`, `pyyaml`
- ✅ Optional deps: `proselint` (local-checks group)
- ✅ Dev deps: `pytest`, `pytest-cov`
- ✅ Migrated to src/editing_with_llms/ layout
- ✅ Entry point: `writing-buddy` CLI command
- ✅ Tests moved to tests/ directory

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
