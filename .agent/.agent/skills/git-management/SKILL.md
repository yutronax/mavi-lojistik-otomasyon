---
name: git-management
description: Professional Git operations, branching strategies, and merge conflict resolution. Use this when starting new tasks or finalizing features.
---

# Git Management Skill

This skill ensures the project history remains clean and features are isolated.

## Instructions
1. **Branch Creation**: When a new task starts, immediately propose a branch name and execute `git checkout -b name`.
2. **Atomic Commits**: Group related changes into small, logical commits rather than one giant "finished task" commit.
3. **Status Checks**: Regularly run `git status` and `git diff` to ensure only intended changes are being tracked.
4. **Safe Merging**:
    - Switch to `main`: `git checkout main`
    - Pull latest: `git pull` (if applicable)
    - Merge: `git merge <feature-branch>`
    - Handle conflicts: If conflicts occur, list them for the user and ask for guidance or resolve if obvious.
5. **Rollback**: If the user is unhappy with the changes on a branch, use `git reset --hard` or `git checkout main` to abandon the branch.
