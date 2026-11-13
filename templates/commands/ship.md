---
description: High-discipline coding execution flow
argument-hint: <task>
---
<!-- reasonix-coding-profile 2.0.0 -->

Execute this coding task with a strict engineering workflow.

Task: $ARGUMENTS

Requirements:
1. Read the relevant code, tests, configs, and logs first.
2. For non-trivial work, state a short plan before editing.
3. Make the smallest correct change and avoid unrelated refactors.
4. Run targeted validation first, then widen validation only when needed.
5. Finish with:
   - change summary
   - verification evidence
   - remaining risks
   - 1-3 reusable lessons

If durable memory candidates appear, list them separately. Do not store secrets, one-off paths, or temporary workarounds.
