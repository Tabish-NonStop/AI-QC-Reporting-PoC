#!/usr/bin/env nextflow
nextflow.enable.dsl=2

process PROMPT_BUILDER {

  publishDir "${params.outdir}/llm", mode: 'copy'

  // A small python image is fine
  container 'python:3.11-slim'

  input:
  val  fastq_header
  path fastqc_data_files
  path fastqc_summary_files
  path multiqc_json

  output:
  path "prompt.txt"

  script:
  """
  set -euo pipefail

  python - <<'PY'
  import json
  from pathlib import Path

  fastq_header = ${fastq_header.inspect()}

  fastqc_data_files = [Path(p) for p in ${fastqc_data_files.collect{ it.toString() }.inspect()}]
  fastqc_summary_files = [Path(p) for p in ${fastqc_summary_files.collect{ it.toString() }.inspect()}]
  multiqc_json = Path(${multiqc_json.toString().inspect()})

  # FastQC modules we want to keep (matches the header line after '>>')
  KEEP = {
      "Per base sequence quality",
      "Per sequence quality scores",
      "Per base sequence content",
      "Per sequence GC content",
      "Adapter Content",
      "Overrepresented sequences",
      "Sequence Duplication Levels",
      "Per base N content",
  }

  def extract_fastqc_modules(text: str) -> str:
      out = []
      current_name = None
      current_block = []
      keep_current = False

      for line in text.splitlines():
          if line.startswith(">>"):
              # flush previous block
              if current_name and keep_current and current_block:
                  out.extend(current_block)
                  out.append("")  # spacer
              # start new block
              current_block = [line]
              # header is like: >>Module Name\\tpass
              header = line[2:].strip()
              current_name = header.split("\\t", 1)[0]
              keep_current = current_name in KEEP
          else:
              if current_block is not None:
                  current_block.append(line)

      # flush last
      if current_name and keep_current and current_block:
          out.extend(current_block)

      return "\\n".join(out).strip() + "\\n"

  # Read MultiQC JSON
  # NOTE: This can be huge. You can either include full JSON or trim to key parts.
  data = json.loads(multiqc_json.read_text(encoding="utf-8"))

  # Optional trimming: keep only top-level keys often useful for FastQC/MultiQC reasoning
  # Comment out if you want the full JSON.
  keep_keys = ["report_saved_raw_data", "report_general_stats_data", "report_plot_data", "config", "versions"]
  trimmed = {k: data.get(k) for k in keep_keys if k in data}

  def dump_json(obj) -> str:
      return json.dumps(obj, indent=2, ensure_ascii=False)

  parts = []

  parts.append("## TASK")
  parts.append(
      "You are a Genomics Sequencing Expert who understands different sequencing files and genomic pipelines. Use the provided FastQC + MultiQC outputs to:\\n"
      "You reply only in plain text. No .md format\\n"
      "1) List issues ranked by severity\\n"
      "2) Provide evidence (quote exact lines/fields)\\n"
      "3) Likely causes\\n"
      "4) Recommended fixes (tools/params)\\n"
      "5) Decide PASS vs REVIEW vs FAIL for downstream analysis\\n"
      "6) Provide suggestions for optimizing the pipeline for better performance"
  )

  parts.append("FASTQ HEADER")
  parts.append(fastq_header if fastq_header else "N/A")
  parts.append("")

  parts.append("MULTIQC JSON (trimmed)")
  parts.append(f"FILE: {multiqc_json}")
  parts.append(dump_json(trimmed))
  parts.append("")

  parts.append("FASTQC SUMMARY FILES")
  for f in fastqc_summary_files:
      parts.append(f" FILE: {f}")
      parts.append(f.read_text(encoding="utf-8", errors="replace").strip())
      parts.append("")

  parts.append("FASTQC DATA (selected modules)")
  for f in fastqc_data_files:
      parts.append(f"FILE: {f}")
      txt = f.read_text(encoding="utf-8", errors="replace")
      parts.append(extract_fastqc_modules(txt))
      parts.append("")

  Path("prompt.txt").write_text("\\n".join(parts).strip() + "\\n", encoding="utf-8")
  print("Wrote prompt.txt")
  PY

  test -s prompt.txt
  """
}
