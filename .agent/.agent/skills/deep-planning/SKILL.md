---
name: deep-planning
description: Advanced task breakdown and architecture planning for complex software requirements. Use this skill when the user asks for a new feature, a large refactor, or a project from scratch.
---

# Deep Planning Skill

This skill guides the agent through an exhaustive planning phase to ensure all edge cases are considered.

## Instructions
1. **Requirement Extraction**: List all explicit and implicit requirements from the user request.
2. **Architecture Diagramming**: Use Mermaid diagrams in the `implementation_plan.md` to visualize data flow and component hierarchy.
3. **Data Schema Phase**: If the task involves storage, define the schema (Prisma, SQL, or JSON) first.
4. **Step-by-Step Breakdown**: Break down the execution into the smallest possible units in `task.md`.
5. **Pre-mortem**: Identify 3 things that could go wrong and add guards for them in the plan.
