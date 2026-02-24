nextflow.enable.dsl=2

params.system_prompt = "${projectDir}/modules/llm_infer/system_prompt.txt"

process LLM_INFER {

    tag "qwen2.5:3b"

    publishDir "${params.outdir}/llm_response", mode: 'copy'

    input:
        path prompt_file

    output:
        path "response.txt"

    script:
    """
    set -euo pipefail

    # Build JSON safely
    jq -n \
      --arg model "qwen2.5:3b" \
      --arg system "\$(cat ${params.system_prompt})" \
      --arg user "\$(cat $prompt_file)" \
      '{
        model: \$model,
        messages: [
          {role: "system", content: \$system},
          {role: "user", content: \$user}
        ],
        stream: false
      }' \
    | curl -s http://localhost:11434/api/chat \
        -H "Content-Type: application/json" \
        -d @- \
    | jq -r '.message.content' > response.txt
    """
}
