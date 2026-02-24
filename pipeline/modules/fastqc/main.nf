nextflow.enable.dsl=2

process FASTQC {

    container 'biocontainers/fastqc:v0.11.9_cv8'

    publishDir "${params.outdir}/fastqc", mode: 'copy'

    input:
    path reads

    output:
        tuple path("${reads.simpleName}_fastqc.html"),
              path("${reads.simpleName}_fastqc.zip"),
              path("${reads.simpleName}_fastqc/fastqc_data.txt"),
              path("${reads.simpleName}_fastqc/summary.txt")

    script:
    """
    set -euo pipefail
    
    echo "Executing FastQC on: ${reads}"
    fastqc ${reads}

    echo "Unzipping FastQC zip to expose fastqc_data.txt"
    unzip -q ${reads.simpleName}_fastqc.zip

    test -s ${reads.simpleName}_fastqc/fastqc_data.txt
    test -s ${reads.simpleName}_fastqc/summary.txt

    echo "FastQC Completed: ${reads.simpleName}"
    """
}