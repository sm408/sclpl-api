# Functional Requirements

## Request execution

- author and run HTTP requests
- support standard auth methods
- preserve request history
- store requests in collections/workspaces

## Environment system

- define named environments
- resolve variables from environment and runtime scopes
- switch environments without mutating request definitions

## Batch execution

- support CSV-driven iteration
- expose current batch row to request and function context

## Function runtime

- load Python functions from filesystem
- support pre-request and post-response execution
- allow auth-token helper functions

## Export system

- export results to JSON and CSV
- support reusable response transformation before export

## Workflow baseline

- support sequential chains first
- allow step-to-step request referencing
- support variable propagation across workflow steps

