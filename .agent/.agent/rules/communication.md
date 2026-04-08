# Communication and Planning Rules

## Planning Mode
- **Task-First**: Always start complex requests by creating/updating `task.md`.
- **Implementation Plans**: For any change involving more than one file or non-obvious logic, create an `implementation_plan.md` and wait for "LGTM" or approval.

## High-Level Understanding
- **Identify Goals**: Before writing code, explicitly state the user's goal in the `task_boundary` summary.
- **Clarification**: If a request is ambiguous, stop and ask questions via `notify_user` before making assumptions.

## Artifact Excellence
- **Conciseness**: Keep `task.md` and `walkthrough.md` updated and concise.
- **Verification**: Every task must end with a verification phase documented in the walkthrough, including terminal outputs or browser recordings if applicable.
