# Architecture Diagrams

This document shows the project layout and agent workflow using GitHub-rendered Mermaid diagrams.

## System Layout

```mermaid
flowchart LR
    User["Analyst / Portfolio User"] --> CLI["CLI Runner<br/>src.orchestrator"]
    User --> API["FastAPI Service<br/>src.api"]
    API --> Orchestrator["Orchestrator<br/>Load workbook, group by L3"]
    CLI --> Orchestrator
    Orchestrator --> Graph["LangGraph State Machine"]
    Graph --> Agent1["Agent 1<br/>Function Tagger"]
    Graph --> Validator["Hybrid Validator<br/>Python checks + LLM review"]
    Graph --> Agent2["Agent 2<br/>ECR Recommender"]
    Graph --> Guards["Deterministic Guards<br/>target checks, mismatch checks"]
    Guards --> Writer["Excel Writer<br/>Summary + ECR Results"]
    Writer --> Output["Excel Output<br/>output/*.xlsx"]
    Output --> Eval["Evaluation Script<br/>scripts/evaluate_output.py"]
    Eval --> Report["Evaluation Report<br/>sample_output/*.md"]
```

## LangGraph Agent Flow

```mermaid
flowchart TD
    Start([Start L3 Cluster]) --> Agent1["Agent 1: Function Tagger<br/>Assign 2-4 word Function labels"]
    Agent1 --> Validator["Hybrid Validator<br/>deterministic checks + LLM review"]
    Validator -->|"valid tags"| Agent2["Agent 2: ECR Recommender<br/>Retain / Eliminate / Consolidate"]
    Validator -->|"tag issues and retries remain"| IncRetry["Increment shared retry counter"]
    IncRetry --> Agent1
    Validator -->|"retry cap hit but tags exist"| Agent2
    Validator -->|"retry cap hit and tags missing"| MaxRetry["max_retries_hit"]
    Agent2 --> Guards["Deterministic ECR Guards"]
    Guards -->|"clean output"| Done([done])
    Guards -->|"Function mismatch in group"| IncRetry
    Guards -->|"retry cap hit"| MaxRetry
    MaxRetry --> End([End With Review Flag])
    Done --> End
```

## Data And Output Flow

```mermaid
sequenceDiagram
    participant U as User
    participant O as Orchestrator
    participant G as LangGraph
    participant A1 as Agent 1
    participant V as Validator
    participant A2 as Agent 2
    participant W as Writer
    participant E as Evaluator

    U->>O: Provide inventory workbook
    O->>O: Normalize columns and group by L3
    loop Each L3 cluster
        O->>G: Invoke graph state
        G->>A1: Generate Function tags
        A1->>V: Submit tags
        V-->>A1: Feedback if tags fail
        V->>A2: Validated tags and cluster context
        A2->>G: ECR decisions
        G->>G: Apply deterministic guardrails
    end
    O->>W: All final cluster states
    W->>U: Excel workbook with Summary and ECR Results
    U->>E: Evaluate generated workbook
    E->>U: Quality metrics and calibration warnings
```

## Responsibility Split

| Component | Responsibility |
| --- | --- |
| `src/orchestrator.py` | Loads Excel, normalizes inventory columns, groups apps by L3, invokes graph, writes final workbook. |
| `src/graph.py` | Builds the LangGraph state machine and shared retry loop. |
| `src/agents/function_tagger.py` | Agent 1. Assigns business Function tags. |
| `src/validator.py` | Hybrid validation for Function tags. |
| `src/agents/ecr_recommender.py` | Agent 2. Produces ECR decisions and applies row-level normalization/repair. |
| `src/output_writer.py` | Writes formatted Excel output and run Summary sheet. |
| `src/api.py` | FastAPI wrapper for upload, run, and download workflows. |
| `scripts/evaluate_output.py` | Computes reliability and calibration metrics from generated Excel output. |

## Repository Layout

```text
.
├── src/
│   ├── agents/
│   │   ├── function_tagger.py
│   │   └── ecr_recommender.py
│   ├── api.py
│   ├── graph.py
│   ├── orchestrator.py
│   ├── output_writer.py
│   ├── schemas.py
│   └── validator.py
├── scripts/
│   ├── create_demo_artifacts.py
│   ├── evaluate_output.py
│   └── run_demo.ps1
├── sample_data/
│   └── app_inventory_demo.xlsx
├── sample_output/
│   ├── ecr_results_demo.xlsx
│   └── evaluation_report_demo.md
├── docs/
├── tests/
├── Dockerfile
└── requirements.txt
```
