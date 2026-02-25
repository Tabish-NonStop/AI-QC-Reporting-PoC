# System Architecture

This document captures the current proof-of-concept architecture across the first-party FrontEnd, BackEnd, and Pipeline layers. It shows how user actions in Streamlit trigger FastAPI run lifecycle APIs, launch the Nextflow workflow, and return a generated MultiQC report for viewing and download.

## Scope

FrontEnd + BackEnd + Pipeline only (first-party scope). External infrastructure and third-party services are intentionally abstracted out.

## Combined Architecture Diagram

```mermaid
flowchart LR
    User[User]

    subgraph FE["FrontEnd - Streamlit"]
        FE_UI[Streamlit App<br/>frontend/streamlit_app.py]
        FE_ACTIONS[Run Controls:<br/>Create / Upload / Start / Refresh / Delete]
        FE_VIEW[Status + MultiQC Viewer<br/>iframe + download links]
    end

    subgraph BE["BackEnd - FastAPI"]
        BE_API[FastAPI Service<br/>backend/app.py]
        BE_META[Run Metadata<br/>meta.json per run]
        BE_RUNS[Runs Storage<br/>pipeline/runs/&lt;run_id&gt;/]
        BE_LAUNCH[Nextflow Launcher<br/>subprocess: nextflow run]
        BE_STATIC[Static Report Serving<br/>/runs mount + download routes]
    end

    subgraph NF["Pipeline - Nextflow DSL2"]
        NF_MAIN[main.nf orchestration]
        NF_HDR[FASTQ_HEADER]
        NF_FASTQC[FASTQC]
        NF_MQC[MULTIQC]
        NF_PROMPT[PROMPT_BUILDER]
        NF_LLM[LLM_INFER]
        NF_FINAL[MULTIQC_REPORT]
    end

    ART_FASTQ[(Uploaded FASTQ)]
    ART_LOG[(nextflow.log)]
    ART_REPORT[(multiqc_final/multiqc_report.html)]

    User --> FE_UI
    FE_UI --> FE_ACTIONS
    FE_ACTIONS -->|POST /api/runs| BE_API
    FE_ACTIONS -->|POST /api/runs/:run_id/upload| BE_API
    FE_ACTIONS -->|POST /api/runs/:run_id/start| BE_API
    FE_ACTIONS -->|GET /api/runs/:run_id| BE_API
    FE_ACTIONS -->|DELETE /api/runs/:run_id| BE_API

    BE_API <--> BE_META
    BE_API <--> BE_RUNS
    BE_API --> BE_LAUNCH
    BE_API --> BE_STATIC
    BE_RUNS -.-> ART_FASTQ
    BE_RUNS -.-> ART_LOG

    BE_LAUNCH --> NF_MAIN
    ART_FASTQ -.-> NF_MAIN

    NF_MAIN --> NF_HDR
    NF_MAIN --> NF_FASTQC
    NF_FASTQC --> NF_MQC
    NF_HDR --> NF_PROMPT
    NF_FASTQC --> NF_PROMPT
    NF_MQC --> NF_PROMPT
    NF_PROMPT --> NF_LLM
    NF_LLM --> NF_FINAL
    NF_FASTQC --> NF_FINAL
    NF_FINAL -.-> ART_REPORT

    ART_REPORT -.-> BE_STATIC
    BE_STATIC --> FE_VIEW
    BE_API --> FE_VIEW
```

Legend:
- Solid arrow: API/control execution
- Dashed arrow: file/data artifact movement

## Runtime Path

1. Create run
2. Upload FASTQ
3. Start Nextflow
4. Poll status/log
5. Produce final MultiQC report with LLM-enriched comment
6. View/download report

## Notes

This is a local PoC architecture with filesystem-based orchestration. Run state and artifacts are persisted under per-run directories, the backend launches Nextflow as a subprocess, and frontend report access is served through backend-managed API and static routes.
