# Policy Engine

The Policy Engine handles client request admission and routing candidates evaluation based on consumer identities, target model groups, and active topology health.

## Responsibilities
- Validate consumer profile configurations and model access scopes.
- Resolve healthy candidate endpoints for a given model group and consumer identity.
- Enforce strict exclusion based on endpoint/account health and manual override flags.

## Data Model & Contracts
- Evaluates constraints defined in `policy_profiles`.
- Implements `get_candidate_endpoints(conn, consumer_id, model_group) -> List[Endpoint]`.

## Observability & Errors
- Logs authorization blocks when consumers request unlisted models.
- Emits debug details during candidate pool compilation.

## Invariants
- Default to deny (least-privilege): If a consumer has no profile, no endpoints are returned.
- A `force-disabled` endpoint is never routed.
- A `force-active` endpoint is always routed unless its parent account is `disabled` or `inactive`.
