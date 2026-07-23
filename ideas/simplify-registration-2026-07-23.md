---
type: idea
project: litellm-control-plane
date: 2026-07-23
status: draft
authors: [@me, @agent]
tags: [antigravity, litellm-control-plane, idea]
refs: [antigravity://conversation/464c5449-9c69-4ec2-b264-8248819a7041]
summary: Proposal to simplify the tedious multi-step resource registration process in the control plane.
impact: Improves developer and operator onboarding experience significantly.
cost-estimate: small
created-by: @agent v1.0
---

# Simplifying Resource Registration and Provisioning

## Background
The current resource registration process (Node, Provider, Account, Model, Endpoint) requires multiple separate REST API calls, making manual provisioning tedious and error-prone.

## Conclusion / Steps
To simplify onboarding, we propose implementing a declarative local synchronization workflow:
- **Declarative Local Manifest (`inventory.yaml`)**: Define a single manifest containing all nodes, accounts, and endpoints.
- **State Reconciliation**: Create a CLI command or API (`POST /registry/sync`) that parses the manifest, compares it with the SQLite database, and applies necessary creations/deletions in a single transaction.

Alternative approaches considered:
- **Batch Import API (`POST /registry/import`)**: Accept a large nested JSON block containing all entities.
- **Cascaded Registrations**: Automatically create missing Models and Accounts when calling `POST /registry/endpoints`.

## Rationale
- GitOps-aligned: Storing configuration in `inventory.yaml` allows versioning and easy replication.
- Reduces manual Swagger UI calls from ~30 down to a single file edit and run command.

## Risks & Assumptions
- Deletions in `inventory.yaml` must be handled carefully (cascading deletes in the database) to avoid orphaned endpoints.

## To-Dos
- [ ] Design the schema for `inventory.yaml` — @me — 2026-08-01
- [ ] Implement the YAML parser and sync controller — @agent — 2026-08-05

## Related Records
- antigravity://conversation/464c5449-9c69-4ec2-b264-8248819a7041
