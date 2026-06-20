# Operating Notes

## Recommended Review Process

After each run:

1. Open the Summary sheet.
2. Check Eliminate and Consolidate counts.
3. Filter `ECR Results` to `Eliminate` and inspect each target in `App to be Retained`.
4. Filter to `Consolidate` and confirm the group anchor makes sense.
5. Review any non-blank Capability Loss values.
6. Review clusters listed as `max_retries_hit` or `error`.

## Calibration Expectations

The orchestrator logs a warning when total Eliminate count is below 5 or Consolidate count is below 10. These thresholds are not automatic fixes. They are a signal that prompts or input quality may need review.

For large, messy enterprise inventories, low single-digit ECR counts are usually suspicious unless the inventory has already been cleaned.

## Cost Control

Run one L3 first when testing prompt changes:

```powershell
.\scripts\run_ecr.ps1 -L3 "Data Integration"
```

Then run the full portfolio after the output style looks right.

## Web Search

Web search is disabled and should remain disabled for this packaged approach. The workflow is calibrated to use portfolio context and prior ECR patterns without external search calls.

## Confidential Data

Do not commit:

- `.env`
- real input workbooks
- generated Excel outputs
- logs
- client-specific review notes unless approved

The calibration file is included because it is part of the approach. Review it before publishing to a public repository.
