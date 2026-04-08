# Project Architecture and Core Purpose

## Core Mission
This project, `portfolioai`, is a dedicated workspace for **Antigravity AI Agent Intelligence and Documentation Management**. Its primary goals are:
1.  **Documentation Repository**: Holding official Antigravity documentation in markdown format within the `docs/` folder for offline and quick-context reference.
2.  **Agent Brain Enhancement**: Using the `.agent/` directory to store custom Rules, Skills, and Workflows that define how the AI (Antigravity) should behave, plan, and remember.

## Technical Architecture
- **Environment**: Local file system based workspace.
- **Documentation**: Markdown-based documentation stored in `docs/`.
- **Agent Intelligence**: 
    - `rules/`: Persistent behavioral guidelines.
    - `skills/`: Specialized task-handling instructions.
    - `workflows/`: Automation scripts and slash-commands.

## Key Behavior Guidelines
- **Self-Correction**: The agent should always check `.agent/rules/` upon starting a session to recall current operating procedures.
- **Documentation Synergy**: When answering questions about Antigravity, the agent must prioritize scanning the local `docs/` before searching the web.
- **Planning-First**: The agent must follow the rules in `.agent/rules/communication.md` for any complex implementation tasks.

## Critical Folders
- `docs/`: Repository of truth for Antigravity features.
- `.agent/`: The persistent memory and behavior engine.
