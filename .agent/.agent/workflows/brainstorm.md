---
description: Run a structured brainstorming session to generate new project ideas or features.
---

# Brainstorming Workflow

This workflow triggers the `idea-generation` skill in a structured loop.

1. Create a new `brainstorm_results.md` artifact.
2. Search for existing Knowledge Items (KIs) related to the current project domain.
3. Call the `idea-generation` skill instructions to generate 5 ideas.
4. Format the results as a "Feature Matrix" table.
5. Use `notify_user` to ask which feature to prototype first.
