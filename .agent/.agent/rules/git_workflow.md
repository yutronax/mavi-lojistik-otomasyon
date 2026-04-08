# Git Branching and Workflow Rules

## Mandatory Branching
- **No Direct Commits to Main**: All new features, bug fixes, or experiments MUST be developed on a dedicated branch.
- **Branch Naming**: Use descriptive names like `feat/new-ui`, `fix/broken-link`, or `experimental/smart-memory`.
- **Checkout Rule**: Before starting any new task, run `git checkout -b <branch-name>`.

## Merging Policy
- **User Approval Required**: The agent is NEVER allowed to merge a branch into `main` automatically.
- **Merge Command**: Only merge when the user explicitly says "Merge this to main" or "Deploy this feature".
- **Cleanup**: After a successful merge, the feature branch should be deleted unless the user requests otherwise.

## Session Persistence
- **Final Commit**: At the end of every significant task or session, the agent should commit all changes to the active branch with a clear message.
