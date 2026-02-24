nextflow.enable.dsl=2

process FASTQ_HEADER {

  //container 'alpine:3.20'

  input:
  path reads

  output:
  stdout

  script:
  """
  set -euo pipefail

  case "${reads}" in
    *.gz)
      gzip -cd ${reads} | head -n 1
      ;;
    *)
      head -n 1 ${reads}
      ;;
  esac
  """
}
