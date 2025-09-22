---
trigger: always_on
---

# Master Rules Proxy

This file acts as a proxy to include multiple rule files located outside of `.windsurf/rules/`.  
When the AI assistant loads this rule, it should also load and respect the following rule files:

## Linked Rule Files

- [General Project Rules](../docs/rules/rules.md)  
  Contains overarching project-wide conventions and constraints not tied to PRD or task management.

- [Create PRD Rule](../docs/rules/create-prd.md)  
  Defines how to generate a Product Requirements Document (PRD), including clarifying questions, structure, and output format.

- [Generate Tasks Rule](../docs/rules/generate-tasks.md)  
  Explains how to transform a PRD into a structured task list, including parent tasks, sub-tasks, and relevant files.

- [Process Task List Rule](../docs/rules/process-task-list.md)  
  Provides guidelines for maintaining and updating a task list, completion protocol, and commit message format.



## Instructions

- Always consider all of the above rules together.  
- Treat them as part of the rule context whenever generating or processing PRDs, task lists, or development workflows.  
- If one of the linked files is updated, assume the updated version takes precedence over any summaries in this proxy file.