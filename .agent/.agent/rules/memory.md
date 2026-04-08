# Memory and Knowledge Management Rules

## Knowledge Item (KI) Usage
- **Check Summaries First**: Before starting any research or implementation, ALWAYS check the `KI summaries` provided at the start of the conversation.
- **Study Relevant Artifacts**: If a KI is relevant, read its artifacts in the `docs/` or `knowledge/` directory before doing independent research.
- **Update Knowledge**: When a new pattern is established or a complex problem is solved, ensure the Knowledge Subagent is aware (by summarizing well in the walkthrough) to trigger KI updates.

## Workspace Context
- **Respect .agent Directory**: Always look for instructions in `.agent/rules` and `.agent/skills` to stay aligned with the user's preferred workflows.
- **Link Documentation**: When referring to concepts, link to the local `docs/*.md` files for quick reference.
