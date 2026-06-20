# ECR Workflow Approach

## Goal

For each application in an inventory, produce a portfolio-specific ECR decision:

- `Retain`: the app is needed and has no better replacement in the same L3 cluster.
- `Eliminate`: the app is superseded by another named app in the same L3 cluster.
- `Consolidate`: two or more rows represent the same product, instance family, duplicate, version, or deployment group.

The workflow is intentionally cluster-based. A recommendation is made using the apps that share the same L3 because ECR decisions depend on the current client portfolio, not generic product knowledge alone.

## LangGraph Flow

The graph processes one L3 cluster at a time.

1. `agent_1`: Assigns Function tags.
2. `validator`: Checks tag quality.
3. `agent_2`: Produces ECR recommendations.
4. `route_after_ecr`: Sends the cluster back to Agent 1 only when ECR exposes a Function mismatch.
5. `output_writer`: Writes one Excel workbook after all clusters finish.

This is a bidirectional design. Agent 2 does not edit Function tags directly because Function tags are shared state owned by Agent 1 and validated by the validator. If Agent 2 finds that an Eliminate or Consolidate group has incompatible Function tags, the graph routes back to Agent 1 with feedback.

## Agent 1: Function Tagger

Agent 1 creates short business Function labels, usually 2 to 4 words. The labels should be more specific than L3 but not overly narrow. These labels help find duplicates, replacement pairs, and same-capability app groups.

Examples:

- L3 `Data Integration`, Function `ETL Platform`
- L3 `Accounts Receivable`, Function `Payment exception review`
- L3 `Identity Management`, Function `Access provisioning`

## Validator

The validator combines deterministic checks and LLM review.

Deterministic checks include:

- Every app must have a Function tag.
- Function cannot exactly equal the L3 text.
- Function must be a usable short label.
- The Function equal-to-L3 check is exact string equality, not semantic similarity.

LLM validation is used for softer quality checks, such as whether a tag is too vague, too technical, or inconsistent with nearby apps.

## Agent 2: ECR Recommender

Agent 2 scans the whole L3 cluster before making decisions. It looks for:

- Legacy or deprecated apps next to modern, strategic, cloud, or successor apps.
- Older versions next to newer versions.
- On-prem apps next to cloud or SaaS counterparts.
- Duplicate rows, repeated descriptions, same-vendor same-capability apps, or separate rows for the same product across instances or regions.
- Product-specific rows that should roll into one primary platform record.

For Consolidate groups, the retained anchor row is also marked `Consolidate`. Its `App to be Retained` value points to itself. This makes group consolidation easier to filter in Excel.

## Deterministic Guards

After Agent 2 returns output, Python guardrails normalize and repair unsafe cases:

- Unknown app names are rejected or repaired with canonical matching.
- Eliminate is accepted only when the retained target exists in the same L3 cluster and is not the eliminated app itself.
- Eliminate targets are matched case-insensitively with whitespace tolerance.
- Eliminate or Consolidate Function mismatches are sent back to Agent 1.
- Blank Capability Loss is allowed for Retain, Consolidate, and clean Eliminate rows.

## Retry Budget

The graph uses a shared retry budget of five loops per L3 cluster. The retry counter increments in one place only, the `increment_retry` graph node. If the cap is hit, the cluster can still produce reviewable output with status `max_retries_hit`.

## Status Values

- `done`: cluster completed cleanly.
- `max_retries_hit`: cluster hit the retry cap and output is accepted with a review flag.
- `error`: an exception occurred, such as API failure or malformed response after retry.
