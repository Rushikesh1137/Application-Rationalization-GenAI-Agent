# Prior ECR Calibration Notes

Source workbook: 

These notes capture reusable decision logic only. They must not be used to copy a prior client's decision for the same app into a new client. ECR remains client-portfolio specific.

## Profile

- Rows reviewed: 388
- Decisions: 251 Retain, 94 Eliminate, 43 Consolidate
- Missing descriptions: 291 rows, 75.0%
- Missing Function / Capability: 247 rows, 63.7%
- Missing rationale: 0 rows
- L3 clusters: 52

## Key Calibration Learning

Prior accepted ECR is much more aggressive than a description-only approach. It often made Eliminate and Consolidate decisions from portfolio context, product-family relationships, standard-platform logic, and rationale evidence, even when descriptions were missing.

## Reusable Eliminate Patterns

- Eliminate can be appropriate when a point solution, niche tool, older tool, or overlapping product is covered by a broader enterprise standard platform in the same client portfolio.
- Literal "replaced by" wording is not required when the retained app is clearly the standard platform for the same Function or L3 capability.
- Common eliminate rationales include reducing tool sprawl, reducing license cost, removing duplicate functionality, standardizing governance, and consolidating overlapping integrations.
- Strong eliminate signals include overlapping observability/APM tools, point CRM tools into enterprise CRM, social listening tools into integrated social platform, niche cloud security tools into cloud security standard, older payment or integration tools into enterprise gateway/integration platform, and redundant print/document tools into an enterprise print/document platform.
- A blank source description should not automatically force Retain if app name, L3, Function, retained target, and peer portfolio context provide enough evidence.
- Eliminate still requires a retained app in the same current client inventory. Do not transfer prior-client replacement targets directly.

## Reusable Consolidate Patterns

- Consolidate is appropriate for duplicate product rows, vendor placeholder rows, modules of the same suite, environment or instance rows, overage or billing rows, and separate entries for the same product family.
- Prior ECR frequently consolidates product modules or named instances into a parent product/platform record.
- Same vendor plus similar product name plus same Function is enough to consider Consolidate, even without an explicit duplicate flag.
- If one row is the retained anchor of a consolidation group, our output schema should mark that anchor as Retain. Only duplicate/module/instance rows should be Consolidate.

## Reusable Retain Patterns

- Retain the enterprise standard platform or parent product that survives an Eliminate or Consolidate group.
- Retain when the app has a unique specialized capability, is a core operational platform, or there is no clear same-client replacement.
- Retain when evidence is too weak to prove duplicate, overlap, or replacement.
- Retain can be correct even when rationale mentions a broader rationalization group, if the row itself is the surviving target.

## Guardrails

- Do not hardcode app-specific prior decisions.
- Same app names can have different ECR decisions for different clients.
- Use prior ECR only to calibrate what evidence is strong enough.
- Current client inventory, L3 cluster, Function tags, descriptions, and named retained apps remain the source of truth.
