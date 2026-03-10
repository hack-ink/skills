---
name: research-pro
description: Use when the user needs architecture/research guidance from the latest ChatGPT Pro model via chatgpt.com Projects, especially for design tradeoffs where Codex should consult Pro externally. Trigger on requests like "ask Pro", "chatgpt pro", "research-pro", or "consult Pro model".
---

# Research Pro

## Objective

Get decision-grade research and architecture recommendations from ChatGPT Pro, then bring the result back into Codex execution.

## Inputs

- The decision/question to evaluate (what you must decide).
- Existing materials to incorporate (docs/links/code pointers/logs), summarized or pasted (redact secrets).
- Constraints, success criteria, and non-goals (timebox, budget, platform, security/compliance).
- Optional Project name override (default derived as `org/project`).
- Memory mode: `project-only` (default) or `Default` only if explicitly requested.

## Browser transport

- Treat plain `agent-browser` and `scripts/agent-browser-node.sh` as command-compatible entrypoints.
- Use plain `agent-browser` only when it is already known-good on the current host.
- Do **not** add `--native` as a generic fix. `--native` only changes daemon mode; it does not guarantee a different global entrypoint, and a running daemon can ignore it.
- For long-lived Project flows, flaky native hosts, or any run where you need deterministic Node/Playwright behavior, prefer `scripts/agent-browser-node.sh`.

## Hard gates

### Execution + safety (must follow)

1. Default to running the Pro consultation in the current thread.
   - Subagents can be terminated by the runtime before a long Pro run completes, which can look like a hang to the parent.
   - Use a Runner subagent only for short, bounded steps (navigation + prompt submission) and return early; do not wait for Pro completion inside the subagent.
   - Single-flight: do not start a second Pro run until the current one is completed or explicitly aborted.
   - Once the target Project is ready and prompt submission is in scope, stop using short probe scripts that exit the browser between steps. Keep one continuous browser session alive through prompt submission, polling, and extraction.
   - If a Runner subagent is used, do not close/replace it just because it is quiet; wait patiently and avoid starting a new Pro chat “because it seems stuck”.
   - If a Runner subagent is used, have it return `conversation_url` as soon as it exists (after prompt submission) so the parent can take over polling.
   - If the Runner subagent is interrupted/terminated, assume ChatGPT may still be generating in the background:
    - First, attach to the existing browser session and recover the URL via `agent-browser --session research-pro --session-name research-pro get url`.
     - If the URL already contains `/c/`, treat it as the canonical `conversation_url` and resume polling; do not start a new chat.
     - Only start a new chat after you have evidence the existing conversation cannot be recovered or is explicitly aborted.
   - If `agent-browser` itself is unhealthy before page interaction starts (for example trivial local commands like `--help`, `session list`, `get url`, or a minimal `open` hang/fail), treat that as a client/daemon transport failure, not as a ChatGPT page problem.
   - In that case, fall back to direct Playwright control using the same `research-pro` Chrome profile directory and keep that browser context alive for the rest of the run. Reuse any existing Project or conversation you already created; do not restart from scratch unless the session is unrecoverable.
   - Active-generation controls are authoritative. Do not treat partial output, a visible `Copy` button, or the absence of progress text as completion while `Stop streaming`, `Continue generating`, `Update`, or equivalent active-generation controls remain.
   - Exact reattach rule: if the canonical `conversation_url` still resolves to a live `/c/` thread and `snapshot -i -C` shows that a Pro model is selected, `Extended` thinking is active, and a live `Stop streaming` control is present, the consultation is definitively `in_progress`, not complete, even if a `Copy` button and partial assistant text are visible.
2. Treat secrets and private data as sensitive: do not paste tokens, credentials, internal-only identifiers, customer data, or private URLs.
3. No leaks in web research: do not include sensitive details in any “search log” or “sources” requests to Pro.

### ChatGPT Project contract (must follow)

4. Always use `chatgpt.com` Projects; do not run the consultation outside a Project.
5. Use headed browser automation for ChatGPT (`--headed --args "--disable-blink-features=AutomationControlled"`), with an isolated daemon session via `--session research-pro`, persisted browser state via `--session-name research-pro`, and a dedicated profile path via `--profile ~/.agent-browser/profiles/research-pro` (absolute path preferred).
   - `--session research-pro` isolates the live daemon/browser session. `--session-name research-pro` only names the saved browser state; it is not a substitute for session isolation.
   - Avoid relative profile paths: they change with `cwd` and can load the wrong persisted login state.
   - Keep session/profile identifiers aligned to the skill name (`research-pro`) for recognizability.
   - `scripts/agent-browser-node.sh` is the supported drop-in fallback when you need to force the JS wrapper / Node daemon / Playwright path.
6. Use project name format `org/project` unless the user explicitly overrides this rule.
7. Derive project name in this order:
   - explicit user value (validate format),
   - git remote origin normalized to `org/project`,
   - fallback `local/<cwd-basename>`.
8. Search existing Projects before creating a new one; avoid duplicates.
9. Default Project memory to `project-only`; switch to `Default` only when the user explicitly asks.
   - Project memory is immutable after creation ("This cannot be changed"), so it must be set during creation.
   - Do **not** spend time checking `Project settings` for existing Projects unless the user explicitly asks to verify memory mode.

### Pro model + latency (must follow)

10. Ensure the latest available Pro model is selected, then set Pro thinking to `Extended` by default.
   - Switch to `Standard` only if the user explicitly asks for `Standard`/`default`.
11. Poll every 180 seconds while waiting for completion because Pro Standard can still take minutes to hours.
   - There is no fixed polling budget or max cycle count. Keep polling the same conversation until the completion gate passes, the run is explicitly aborted, or a real `needs-user-action` blocker is reached.

## Procedure

### A) Build the Pro prompt (mirror `research` methodology)

Ask Pro to follow this workflow and to be explicit about evidence:

1. **Intake + scope**: restate the decision to be made; define success criteria, constraints, and non-goals.
2. **Read first**: incorporate the provided materials (or explicitly state “none provided”).
3. **Confirm the pain**: list pain points and confirm they match the ask.
4. **Clarify unknowns**: ask the smallest set of high-leverage questions if anything blocks correctness.
5. **Set evaluation criteria**: define criteria (security, reliability, latency, DX, cost, migration complexity, operational burden).
6. **Option survey**: present **2–4** viable options with tradeoffs.
7. **Synthesize + recommend**: make a clear recommendation, plus conditions where you’d choose differently.
8. **Evidence map**: for each major claim, provide `claim -> evidence -> source`.
   - Prefer **3+ independent sources** when browsing is possible; otherwise label limitations.
   - If a claim can’t be supported, label it a hypothesis and say what would confirm/deny it.
9. **Risks + mitigations**: include rollout/migration notes when relevant.
10. **Next steps**: concrete actions.

### B) Open ChatGPT + ensure login

1. Open ChatGPT in headed mode and verify login.
   - Recommended invocation: `agent-browser --headed --args "--disable-blink-features=AutomationControlled" --session research-pro --session-name research-pro --profile ~/.agent-browser/profiles/research-pro open https://chatgpt.com`
   - Stable Node/Playwright fallback: `scripts/agent-browser-node.sh --headed --args "--disable-blink-features=AutomationControlled" --session research-pro --session-name research-pro --profile ~/.agent-browser/profiles/research-pro open https://chatgpt.com`
   - Use a dedicated absolute profile directory plus both `--session research-pro` and `--session-name research-pro`; relative profile paths vary by `cwd` and can reuse the wrong browser state.
   - If the CLI reports `--args ignored: daemon already running`, the existing browser daemon is being reused; run `agent-browser --session research-pro close` first when you need a fresh launch with new args.
   - During reattach/polling, do not treat a busy-daemon or similar transient CLI warning as completion. Reuse the existing session, recover `conversation_url`, and continue polling the same thread.
   - If the plain `agent-browser` client/daemon path is the thing that is broken, switch to `scripts/agent-browser-node.sh` with the same args and profile before dropping all the way to custom Playwright automation.
2. If login is required, pause for manual login/MFA and continue after success.

### C) Open or create the target Project (with correct memory at creation)

1. Ensure the left sidebar is visible before project selection/creation.
   - If you see `Open sidebar`, click it.
   - If `Open sidebar` is not visible because the sidebar is hover-revealed, move the mouse to the top-left (for example: `agent-browser --session research-pro --session-name research-pro mouse move 10 10`), run `agent-browser --session research-pro --session-name research-pro snapshot -i -C` again, then click `Open sidebar`.
   - Prefer `snapshot -i -C` while working in the sidebar because Project/sidebar entries can be cursor-interactive.
   - Do not trust raw text presence alone. ChatGPT can leave sidebar/project text in the DOM while the visible control is collapsed or not currently actionable; confirm state with clickable snapshots, screenshots, and actual URL/state changes.
2. Take `snapshot -i -C`.
3. Find/click existing project first.
   - If clicking the Project link is blocked by overlays, take a non-interactive `snapshot` (without `-i`) to capture the Project link `/url: ...`, then run `agent-browser --session research-pro --session-name research-pro open <that-url>` in the same `research-pro` session/profile started in step B.
   - If the Project is not visible because it is under the sidebar `More` entry:
     - Click the `More` sidebar entry under `Projects` (it typically opens a menu of all Projects).
     - If clicks are flaky/blocked, you can open the `More` menu via JS in the current page:
       - `agent-browser --session research-pro --session-name research-pro eval '(() => { const els=[...document.querySelectorAll(\"[data-sidebar-item=\\\"true\\\"][aria-haspopup=\\\"menu\\\"]\")]; const more=els.find(el => (el.textContent||\"\").trim()===\"More\" || (el.textContent||\"\").includes(\"More\")); more?.click(); return {found:!!more, ariaExpanded: more?.getAttribute(\"aria-expanded\")||null}; })()'`
    - Run `agent-browser --session research-pro --session-name research-pro snapshot -i -C` and click the `menuitem "<project-name>"` entry (for example `menuitem "sample-project"`), then proceed.
4. If missing, use the sidebar `New project` entry (often cursor-interactive, not always a button).
   - Use `find text "New project"` plus `snapshot -i -C` patterns when needed.
5. On project creation, set memory during creation:
   - In the `Create project` dialog, click the unlabeled expand button next to the title (it reveals the `Memory` radio group).
   - The dialog may contain hidden inputs, including file inputs. Do not target generic `input` refs blindly; interact only with the title field, the expand/settings control, and the explicit memory radio options.
   - Select `Project-only` (or `Default` only if explicitly requested).

### D) Start a fresh chat + set Pro thinking

1. Start a fresh chat in the selected Project for each consultation unless the user requests continuing an existing thread.
   - Stay on the Project page (URL like `/g/.../project`) with the `Chats` tab selected.
   - Do not use left-sidebar `New chat` here; it navigates to Home (`https://chatgpt.com/`) and leaves the Project.
   - Use the Project-page composer and send the first message to create the new Project-scoped conversation.
2. Select Pro model from the model selector button (`Model selector, current model is ...`).
3. Click the Pro pill near the composer and set thinking to `Extended` by default.
   - Switch to `Standard` only if the user explicitly asks for `Standard`/`default`.

### E) Submit + poll

1. Submit the prompt.
2. Immediately capture and persist `conversation_url` (single-flight lock):
   - Run `agent-browser --session research-pro --session-name research-pro get url` and treat that as the canonical `conversation_url`.
   - If the run is using Playwright fallback instead of `agent-browser`, capture the live page URL directly from that browser context and treat it as the canonical `conversation_url`.
   - If navigation breaks or UI drifts, reopen `conversation_url` instead of starting a new chat.
3. Poll every 180 seconds until completion:
   - There is no fixed polling budget or max cycle count. The same turn keeps polling until the completion gate passes, the run is explicitly aborted, or a real `needs-user-action` blocker is reached.
   - Keep the same browser context open while polling. Do not revert to "probe, close, reopen" once prompt submission is in scope.
   - Completion gate: do not treat partial visible assistant text, a visible `Copy` button, or missing progress text as completion while `Stop streaming`, `Continue generating`, `Update`, or equivalent active-generation controls are still present.
   - Reattach gate: if `agent-browser --session research-pro --session-name research-pro get url` still returns the same `/c/` thread and `snapshot -i -C` shows that a Pro model is selected, `Extended` thinking is active, and `Stop streaming` is present, the consultation is still active. Keep polling in the same turn. Use `status=in_progress` only when an explicit interruption, checkpoint, or continuity handoff is required.
   - If polling hits a transient `agent-browser` failure (busy daemon, snapshot failure, temporary transport error, or session hiccup), recover the existing session first:
     - Run `agent-browser --session research-pro --session-name research-pro get url`.
     - If it still returns a `/c/` conversation, reopen or resume that URL in the same session and continue polling.
     - Do not conclude completion and do not start a new chat unless recovery fails repeatedly or the run is explicitly aborted.
   - If generation is still running (`Stop streaming`, "still generating", or equivalent), keep waiting.
   - If a `Pro thinking` panel appears with `Update`/`Stop`, just wait; do not spam `Update`.
   - If `Continue generating` appears, click it and continue polling.
   - After active-generation controls are gone and the page shows a stable idle state (`Done` or equivalent), take a snapshot to capture the final answer state.
   - Safe extraction only after completion: do not use `agent-browser get text body` on ChatGPT pages. Prefer the assistant-message `Copy` button after the completion gate passes; if that is unavailable, use DOM-scoped extraction that targets only the completed final assistant message.
   - Avoid spamming output; only report when content changes or completes.
   - Do not start a new chat just because the current one is slow; waiting is expected.

### F) Return a decision-ready handoff to Codex

Return:
- conversation URL
- status:
  - `completed`: normal terminal success state; the completion gate passed and the final answer was extracted
  - `needs-user-action`: normal terminal blocked state; login/MFA/UI recovery/manual intervention prevents continued polling
  - `in_progress`: non-terminal continuity/checkpoint state only when polling is explicitly interrupted or handed off; if you can still reattach and wait in the same turn, do not stop here
- final answer (full text only when `status=completed`)
- partial answer text (optional and clearly labeled only when `status=in_progress`)
- a short summary
- the evidence map + source links
- explicit assumptions and open questions

### G) Cleanup the temporary browser

Use the dedicated `research-pro` browser session as a temporary worker, not a persistent background browser.

1. On `status=completed`:
   - After the final answer has been extracted and the handoff payload is ready, close the dedicated browser session: `agent-browser --session research-pro --session-name research-pro close`
   - If close fails because the session is already gone, record that and continue; do not treat cleanup failure as a failed research run.
2. On `status=in_progress`:
   - Do **not** close the browser; continuity depends on being able to reattach to the same session and `conversation_url`.
3. On `status=needs-user-action`:
   - Keep the browser open if the user still needs the live page for login/MFA/manual recovery.
   - Close it only after the user-action path is abandoned, explicitly aborted, or converted into a completed handoff.

### H) UI drift resilience (when navigation fails)

ChatGPT UI can change. Do not hardcode brittle selectors as the only path. When any step fails (missing sidebar, `More` menu not opening, clicks blocked by overlays), switch strategies and capture an evidence pack so the **next LLM iteration** can self-heal the automation and/or update this skill.

1. **Capture evidence (always)**
   - `agent-browser --session research-pro --session-name research-pro get url`
   - `agent-browser --session research-pro --session-name research-pro snapshot -i -C` (interactive + cursor-interactive; best for sidebars/menus)
   - `agent-browser --session research-pro --session-name research-pro snapshot` (non-interactive; includes `/url: ...` for links)
   - `agent-browser --session research-pro --session-name research-pro screenshot --annotate` (fast visual of what is intercepting clicks)
2. **Switch strategy (preferred order)**
   - Ensure sidebar is visible (hover top-left if needed) and retry.
   - If a Project is under `More`, open the `More` menu and select the `menuitem "<project-name>"`.
   - If clicking is blocked, use `/url: ...` from non-interactive `snapshot` and `agent-browser --session research-pro --session-name research-pro open <that-url>`.
   - If DOM text and rendered UI disagree, trust rendered/clickable evidence over hidden text nodes: `snapshot -i -C`, annotated screenshots, URL transitions, and actual control-state changes.
3. **Stop conditions**
   - After a small number of retries (2–3), return `status=needs-user-action` and include the evidence pack in the handoff so the next LLM run can patch the workflow.

## Prompt template

Use this as the default payload to Pro (replace placeholders). Keep it strict and structured.

```text
You are a research assistant helping with a technical decision. Follow this workflow strictly and produce a decision-ready recommendation with explicit evidence.

Decision to make:
<question>

Context:
<current system + constraints + non-goals>

Existing materials (summarized; redact secrets):
<docs/links/code pointers/logs or "none">

Please respond with:
1) Problem restatement
2) Pain points (confirmed)
3) Constraints + success criteria + non-goals
4) Open questions (ask only if needed; otherwise state assumptions)
5) Evaluation criteria (security, reliability, latency, DX, cost, migration complexity)
6) Options considered (2–4) with tradeoffs (cost, complexity, risk, migration burden, operational burden)
7) Recommendation + when you’d choose differently
8) Evidence map: claim -> evidence -> source (use 3+ independent sources when possible; include links)
9) Risks + mitigations (include rollout/migration notes if relevant)
10) Concrete next steps

Appendix:
- Search log (query strings + date) if you browse
- Sources list (title + publisher + date + link)
```

## Output contract

Return a compact handoff:

- `project_name`
- `conversation_url`
- `status` (`completed`, `needs-user-action`, or `in_progress`; use `in_progress` only for explicit interruption/checkpoint/continuity handoff)
- `answer_summary`
- `full_answer_text` (only when `status=completed`)
- `partial_answer_text` (optional, only when `status=in_progress`, clearly labeled partial)
- `evidence_links`
