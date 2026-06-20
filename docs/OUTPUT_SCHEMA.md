# Output Schema

The generated Excel workbook contains two sheets.

## Summary

The `Summary` sheet contains:

- Run timestamp
- Total apps processed
- Counts by Recommendation
- Counts by L3
- Clusters that hit max retries
- Capability Loss warnings or auto-corrected rows

## ECR Results

| Column | Meaning |
| --- | --- |
| App Name | Exact application name from the input workbook. |
| Final L3 | L3 cluster used for the recommendation. |
| Function | Short 2 to 4 word label describing what the app does. |
| Recommendation | `Retain`, `Eliminate`, or `Consolidate`. |
| Rationale | 1 to 2 business-friendly sentences explaining the decision. |
| App to be Retained | The surviving app or consolidation anchor. For Retain, this is the same as App Name. |
| Capability Loss if Eliminated | Warning text only when elimination would lose a specific capability not covered by the retained app. Usually blank. |

## Recommendation Semantics

`Retain` means the app remains as a standalone record.

`Eliminate` means another named app in the same L3 cluster covers the capability and should be retained instead.

`Consolidate` means the row belongs to a same-product group, duplicate set, version group, instance group, or platform family. The group anchor is also marked Consolidate and points to itself in `App to be Retained`.

## Formatting

The workbook freezes headers, wraps rationale text, and adds the Summary sheet at the front. Capability Loss cells are highlighted only for Eliminate rows where a non-blank warning is present.
