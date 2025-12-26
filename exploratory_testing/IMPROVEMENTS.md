# Improvement Ideas for editing-with-llms

This document contains brainstormed improvements to the LLM-based editing tool. These are ideas to consider, not a concrete roadmap.

## 1. Configuration Management

### Problem
Typing reader definitions repeatedly is tedious. No way to store common configurations.

### Solutions

#### 1.1 Document-Adjacent Config
Create `.editing-config.yaml` alongside documents:
```yaml
reader: "a Bachelor's in mathematics who mostly knows what formal verification is"
checks: [reader, clarity, value]
model: gpt-4o-mini  # cheap for testing
```

#### 1.2 Global Reader Profiles
Store common reader profiles in `~/.config/llm-editor/profiles.yaml`:
```yaml
profiles:
  math-undergrad: "an undergraduate math student with basic calculus knowledge"
  general-tech: "someone with a CS degree but no domain expertise"
  academic-peer: "a peer reviewer in formal methods"
```
Then use: `--reader-profile math-undergrad`

#### 1.3 Auto-detect from Document
Read config from document frontmatter or special comments:
```markdown
---
reader: "a Bachelor's in mathematics"
checks: [reader, value]
---

# My Article
...
```

#### 1.4 Interactive Profile Builder
First-run wizard to create and save common reader profiles.

#### Human Feedback

I believe that we should use editing-config.yaml where we define different profiles for readers including a default. There
should not be a global profile. In many cases, there are many different readers that I have in mind for a single article.

Essentially I was thinking something like
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

Then we could call with `check bachelors-reader test`. This yaml could also be a good place to put the document map.

---

## 2. Output & Suggestion Management

### Problem
It's difficult to find where the suggestions point to in the original document.

### Solutions

#### 2.1 Structured Output Format
Output JSON with precise locations:
```json
{
  "checks": [
    {
      "type": "clarity",
      "location": {
        "line": 15,
        "column": 23,
        "context": "The process was completed, but..."
      },
      "issue": "[The process was completed...] - This sentence has multiple nested clauses that obscure the main point.",
      "severity": "medium"
    }
  ]
}
```

#### 2.2 Line Number References
Modify prompts to ask LLM to include line numbers:
- Prepend line numbers to input text
- Ask LLM to reference them in output
- Example: "Line 15: [The process was...] - Issue description"

#### 2.3 Diff-Style Output
Generate output that shows context around each issue:
```
Line 12-16:
  12 | The team met to discuss the project.
  13 | The process was completed, but the results,
> 14 | which were unexpected, led to further questions
  15 | about the initial assumptions.
  16 | Everyone agreed to meet again.

Issue: [Line 13-15] - This sentence is unclear due to...
```

#### 2.4 Interactive Review Mode (TUI)
Terminal UI for navigating issues:
- Show document with highlighted issues
- Jump between issues
- See explanation for each
- Mark as reviewed/ignored

#### 2.5 Editor Integration Markers
Output in format that editors can consume:
- LSP (Language Server Protocol) diagnostics
- Compiler-style warnings: `file.txt:15:23: clarity issue: unclear sentence`
- VS Code problem matcher format

#### Human Feedback

I think that output for LSP or compiler-style warning would be ideal, but it would be nice to have a diff style output where
we can highlight the words with color in the terminal. They should use the same underlying data model.

I'd be interested in how you (as in Claude Code) format your tool calls for edits already. That could be a good starting place,
but remember we are mainly here to show the problems, not to provide solutions.

##### Your Reponse


---

## 3. Chunking & Document Structure

### Problem
Long documents can't be processed effectively. Can't check specific sections. No way to provide context from earlier parts.

### Solutions

#### 3.1 Smart Chunking Strategies
- **Semantic boundaries**: Split by headers, paragraphs, sections
- **Overlapping windows**: Include previous/next section for context
- **Hierarchical**: Check document structure first, then drill down
- **Configurable chunk size**: Based on token limits

#### 3.2 Section-Specific Checks
```bash
# Only check specific sections
--section "Introduction"
--lines 1-50
--paragraph 3

# Include context from earlier sections
--section "Methods" --context-before 2
```

#### 3.3 Summarization for Context
When checking section 5:
- Generate summary of sections 1-4
- Include summary as context for coherence checking
- Cheaper than including full text
- Maintains narrative flow awareness

#### 3.4 Document Map Generation
Two-pass approach:
1. First pass: Create structure outline
2. Second pass: Check each section with outline as context
3. Useful for checking coherence across document

#### 3.5 Progressive Checking
```bash
# Quick check of just the introduction
--preview

# Full document check with summaries
--full

# Deep check with full context
--deep-context
```

#### Human Feedback

I like the idea of document map genreation, but I don't think we really have to worry about this yet. We
should definitely keep it in mind though for later.

---

## 4. Interactive Modes

### Problem
Currently one-shot CLI tool. No way to iteratively work with results.

### Solutions

#### 4.1 TUI (Terminal User Interface)
Like `lazygit` or `tig`:
- Navigate through document
- Jump between flagged issues
- See issue explanations
- Mark issues as reviewed/ignored
- Side-by-side view of text and issues

#### 4.2 Watch Mode
```bash
python llm_typo_checker.py --watch --check clarity myfile.txt
```
- Re-run checks on file save
- Useful during active writing
- Show diff of what changed
- Only re-check modified sections

#### 4.3 REPL Mode
```
> load myfile.txt
> check typo
Found 3 issues
> check reader --reader "high school student"
Found 7 accessibility issues
> show issue 1
> save-results myfile-issues.json
```

#### 4.4 VS Code Extension
- Real-time checking as you type (debounced)
- Inline diagnostics (squiggly underlines)
- Problems panel showing all issues
- Hover to see explanations
- Command palette integration
- Status bar showing check status

#### Human Feedback

While I like the idea of a VS code extension, I don't think we need to care about this yet.

---

## 5. Hybrid Approach: Fast + Smart Checks

### Problem
LLMs are expensive and slow for basic errors. Might want faster feedback for simple issues.

### Solutions

#### 5.1 Two-Tier Checking
**Fast local checks** (instant, free):
- `pyspellchecker` or `aspell` for spelling
- `language-tool-python` for grammar
- `textstat` for readability metrics
- `proselint` for style issues

**LLM checks** (slower, costs API calls):
- Reader accessibility
- Value assessment
- Clarity with reader context
- Function evaluation

#### 5.2 Progressive Enhancement
```bash
# Quick pass - local tools only
--quick

# Full pass - local + LLM checks
--full

# Selective LLM - only specific checks
--llm-only clarity,reader
```

#### 5.3 Cost Optimization
- Use cheap models (Haiku, GPT-4o-mini) for first pass
- Flag uncertain issues for expensive model review
- Cache results to avoid re-checking unchanged sections
- Only send changed paragraphs on incremental checks

#### Human Feedback

We need to do a lot of testing here. I'm quite concerned about how this interacts with code especially;
usually I am writing in markdown, LaTeX, Typst (LaTeX alternative), or in Lean 4's documentation language.
How can we put things in the right form here?

These also have their own configuration that needs to be made available. I suspect that we'll also want some custom
instructions too (things like specific warnings to ignore, etc).

##### Your Response


---

## 6. Workflow Enhancements

### New workflow capabilities

#### 6.1 Batch Mode
```bash
# Check all markdown files
--batch "*.md" --check reader --reader "general audience"

# Check all files in directory
--batch docs/ --recursive
```

#### 6.2 CI/CD Integration
- GitHub Action to check docs in PRs
- Fail if critical issues found
- Comment with flagged issues
- Track improvement over time

#### 6.3 Comparison Mode
```bash
# Compare two versions
--compare draft.txt final.txt
# Show what improved, what got worse
```

#### 6.4 Learning Mode
- Track common issues over time
- Identify personal writing patterns
- "You often write sentences with nested clauses"
- Suggest focus areas for improvement

#### 6.5 Multi-Document Consistency
```bash
# Check terminology consistency across files
--consistency docs/*.md

# Check if tutorial series maintains consistent reader level
--series-check tutorial-*.md
```

#### Human Feedback

I don't see these as necessary yet.

---

## 7. Enhanced Check Types

### New types of checks to add

#### 7.1 Tone Consistency
Check if tone is consistent throughout document.

#### 7.2 Reading Level
Combine Flesch-Kincaid with LLM assessment for specific reader.

#### 7.3 Style Guide Compliance
Check against AP Style, Chicago Manual, or custom style guides.

#### 7.4 Terminology Consistency
Flag inconsistent usage of terms (e.g., "user" vs "customer" vs "client").

#### 7.5 Cross-Reference Validation
Check if all references, citations, or links are valid.

#### 7.6 Fact-Flagging
Flag claims that might need citations or verification.

#### 7.7 Bias Detection
Identify potentially biased or loaded language.

#### 7.8 Structure Analysis
Assess document structure, flow, and organization.

#### Human Feedback

I think some of these are not as useful, and I'm worried about whether LLMs can do this effectively.
The primary goal of writing is to provide value to the readers. If I read another book on writing,
then I will consider adding stuff from there, but this list doesn't quite seem right in my mind.

---

## 8. Technical Architecture Improvements

### Code organization and extensibility

#### 8.1 Modular Structure
```
llm-editor/
  checks/
    typo.py
    clarity.py
    reader.py
    value.py
    ...
  output_formatters/
    json.py
    text.py
    lsp.py
    diff.py
  config/
    profiles.py
    document_config.py
  chunking/
    semantic.py
    token_based.py
  core/
    editor.py
    llm_client.py
```

#### 8.2 Plugin System
Users can add custom checks:
```python
# ~/.config/llm-editor/plugins/custom_check.py
from llm_editor.plugin import Check

class CustomCheck(Check):
    name = "academic-tone"
    system_prompt = "..."

    def format_output(self, result):
        ...
```

#### 8.3 API Mode
Run as a library, not just CLI:
```python
from llm_editor import Editor

editor = Editor(model="gpt-4")
results = editor.check(
    text=my_text,
    check_type="reader",
    reader="undergraduate student"
)
```

#### 8.4 Multiple Output Formats
```bash
--format json
--format text
--format lsp    # Language Server Protocol
--format html   # Annotated HTML
--format diff
```

#### Human Feedback

I'm interested in getting lsp later, but compiler warning style + highlighted sections of text are probably
sufficient for now? I think we should make this a proper package with a uv-style pyproject.toml though,
especially if we are going to use proselint and python_language_tool or whtaever.

---

## 9. Documentation-Specific Features

If primary use case is technical documentation:

#### 9.1 Code Example Validation
- Extract and run code snippets
- Verify they execute without errors
- Check if output matches claims

#### 9.2 Link Checking
Verify all URLs are valid and reachable.

#### 9.3 Image Reference Checking
Ensure all referenced images exist.

#### 9.4 API Documentation Sync
Check if code changes broke documentation examples.

#### 9.5 Version-Specific Docs
Maintain and check multiple documentation versions.

#### Human Feedback

I'm not sure about this yet.

---

## 10. Prompt Engineering Improvements

### Making the LLM checks more effective

#### 10.1 Better Location References
Include line numbers in input to LLM:
```
1  | # Introduction
2  |
3  | This document explains formal verification.
4  | The process was completed, but the results were unexpected.
```
Ask LLM to cite line numbers in responses.

#### 10.2 Severity Levels
Ask LLM to classify issues:
- Critical: blocks understanding
- Medium: causes confusion
- Minor: could be clearer

#### 10.3 Examples in Context
Provide examples of good and bad writing for the specific reader in the system prompt.

#### 10.4 Multi-Step Reasoning
For complex checks, break into steps:
1. Identify potentially unclear sentences
2. For each, explain why it's unclear for this reader
3. Classify severity

#### 10.5 Chain-of-Thought
Ask LLM to explain its reasoning before identifying issues.

#### Human Feedback

What do you get when you read code usually?

We have time to test 1 or 2 strategies.

---

## Implementation Priority Recommendations

### High Impact, Low Effort
1. Config file support (document-adjacent YAML)
2. Line number references in output
3. Section-specific checking (`--lines` flag)
4. Global reader profiles

### High Impact, Medium Effort
1. Interactive TUI for reviewing issues
2. Smart chunking for long documents
3. Watch mode for iterative writing
4. Structured JSON output format

### High Impact, High Effort
1. VS Code extension
2. Hybrid fast+smart checking with local tools
3. Full plugin architecture
4. Document summarization for context

### Nice to Have
1. Batch processing
2. CI/CD integration
3. Learning/analytics mode
4. Comparison mode
