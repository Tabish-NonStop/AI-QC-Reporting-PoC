nextflow.enable.dsl=2

params.reads  = "${projectDir}/data/dataset.fastq"
params.outdir = "${projectDir}/results"

include { FASTQC }         from './modules/fastqc/main.nf'
include { MULTIQC }        from './modules/multiqc/main.nf'
include { FASTQ_HEADER }   from './modules/fastq_header/main.nf'
include { PROMPT_BUILDER } from './modules/prompt_builder/main.nf'
include { LLM_INFER }      from './modules/llm_infer/main.nf'
//include { EMBED_LLM }      from './modules/embed_llm/main.nf'
include { MULTIQC_REPORT } from './modules/multiqc_report/main.nf'

workflow {

  // Input FASTQ
  reads_ch = Channel.fromPath(params.reads)

  // Extract FASTQ header line (stdout -> value)
  fastq_header_ch = FASTQ_HEADER(reads_ch)

  // Run FastQC (emits html, zip, fastqc_data.txt, summary.txt)
  fastqc_out_ch = FASTQC(reads_ch)

  // Split outputs
  fastqc_data_ch    = fastqc_out_ch.map { html, zip, data, summary -> data }
  fastqc_summary_ch = fastqc_out_ch.map { html, zip, data, summary -> summary }
  fastqc_dir_ch     = fastqc_data_ch.map { it.parent }

  // MultiQC expects FastQC directories (collect -> list staged as a path input)
  multiqc_out_ch = MULTIQC(fastqc_dir_ch.collect())

  // Grab multiqc_data.json from MULTIQC outputs
  multiqc_json_ch = multiqc_out_ch.map { report_html, data_dir, json_file -> json_file }
  multiqc_html_ch = multiqc_out_ch.map { report_html, data_dir, json_file -> report_html }


  // Build a single prompt.txt
  prompt_ch = PROMPT_BUILDER(
    fastq_header_ch,
    fastqc_data_ch.collect(),
    fastqc_summary_ch.collect(),
    multiqc_json_ch
  )

  LLM_INFER(prompt_ch)

  //EMBED_LLM(multiqc_html_ch, LLM_INFER.out)

  MULTIQC_REPORT(fastqc_dir_ch.collect(), LLM_INFER.out)
}
