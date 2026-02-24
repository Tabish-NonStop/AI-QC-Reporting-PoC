#!/usr/bin/env nextflow
nextflow.enable.dsl=2

process MULTIQC_REPORT {

  container 'multiqc/multiqc:v1.33'
  publishDir "${params.outdir}/multiqc_final", mode: 'copy'

  input:
  path fastqc_dirs
  path llm_response_txt

  output:
  tuple path("multiqc_report.html"),
        path("multiqc_report_data"),
        path("multiqc_report_data/multiqc_data.json")

  script:
  """
  set -euo pipefail

  cat > multiqc_config.yaml <<'YAML'
  title: "MultiQC Report"
  report_comment: |
  YAML

  sed 's/^/    /' "${llm_response_txt}" >> multiqc_config.yaml

  multiqc \\
    -o . \\
    -c multiqc_config.yaml \\
    --filename multiqc_report.html \\
    "${fastqc_dirs}"

  test -s multiqc_report.html
  test -s multiqc_report_data/multiqc_data.json
  """
}
