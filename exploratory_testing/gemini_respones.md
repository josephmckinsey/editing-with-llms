# Writing Buddy: Architecture & Implementation

This document outlines the integration of an LLM-powered grammar checker into VS Code using a non-intrusive "Review Mode" architecture.

## 1. Core Philosophy: Human-in-the-Loop
To protect the author's voice and manage LLM noise, this tool avoids "live" squiggles and "auto-fixes."
* **Loop Frequency:** 5–15 minute "Scan" cycles triggered via CLI.
* **UI Pattern:** Suggestions appear as "Comment Bubbles" (similar to MS Word or GitHub PRs).
* **Action:** Users must manually edit their text based on the advice, rather than clicking "Apply."

---

## 2. Integration Strategy: The Watcher Pattern
Because the LLM logic is high-latency and noisy, it runs in a standalone process.

1. **CLI (The Brain):** The user runs `writing-buddy check`. The tool generates a report.
2. **The Handshake:** Findings are written to `.writing-buddy/results.json` in the workspace.
3. **Extension (The UI):** A VS Code extension monitors this file using `vscode.workspace.createFileSystemWatcher`.

---

## 3. The Comments API Deep-Dive
The Comments API is the primary vehicle for feedback because it is asynchronous and persistent.

### Key API Classes
* **`CommentController`**: The top-level container that manages the feedback "layer" in the editor.
* **`CommentThread`**: A specific discussion point pinned to a `vscode.Range`. 
* **`CommentMode.Preview`**: Forces the comment to be read-only. This prevents users from treating suggestions as editable text blocks, maintaining the "critique" vs. "editor" boundary.

### UI Interaction
When the JSON file updates, the extension maps the line numbers to `CommentThread` objects. The user sees a small icon in the gutter; clicking it expands a bubble containing the LLM's rationale.

---

## 4. Severity & Confidence Levers
To mitigate the "noisy output" problem, the extension provides two filtering levers (via Settings or Sidebar):

| Lever | Description | Behavior |
| :--- | :--- | :--- |
| **Confidence** | LLM self-score (0-100%) | Only renders comments where the LLM is certain. Filters out hallucinations. |
| **Severity** | Error type (Critical vs. Stylistic) | Allows the user to hide stylistic "opinions" and focus only on spelling/punctuation. |

**Logic:** When a lever is moved, the extension clears the `CommentController` and re-reads the JSON, applying the new threshold filters before re-creating the `CommentThread`s.

---

## 5. Sample JSON Structure
Your CLI should output the following schema to support these controls:

```json
[
  {
    "file": "path/to/prose.md",
    "line": 42,
    "message": "This sentence uses passive voice. Consider revising.",
    "severity": "stylistic",
    "confidence": 0.85
  }
]
