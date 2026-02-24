nextflow.enable.dsl=2

process MULTIQC {
    container 'ewels/multiqc:dev'

    publishDir "${params.outdir}/multiqc", mode: 'copy'
    
    input:
    path fastqc_dirs

    output:
    tuple path("multiqc_report.html"),
          path("multiqc_data"),
          path("multiqc_data/multiqc_data.json")

    script:
    """
    set -euo pipefail
    
    echo "Running MultiQC on FASTQC directories"
    ls -la ${fastqc_dirs} || true
    multiqc ${fastqc_dirs} -o .
    
    test -s multiqc_data/multiqc_data.json

    echo "MultiQC done"
    """
}