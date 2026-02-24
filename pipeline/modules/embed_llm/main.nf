nextflow.enable.dsl=2

process EMBED_LLM {

  publishDir "${params.outdir}/multiqc_with_llm", mode: 'copy'

  input:
    path multiqc_html
    path llm_response

  output:
    path "multiqc_report_with_llm.html"

  script:
  """
  set -euo pipefail

  python3 - <<'PY'
from pathlib import Path
import html

raw = Path("${llm_response}").read_text(encoding="utf-8", errors="replace")
escaped = html.escape(raw)

block = '''
<div id="llm-summary" style="margin:16px; padding:16px; border:1px solid #444; border-radius:10px; background:#111; color:#fff;">
  <div style="display:flex; align-items:center; justify-content:space-between; gap:12px;">
    <div style="font-size:16px; font-weight:700;">LLM QC Summary</div>
    <button id="llm-toggle" type="button"
      style="cursor:pointer; padding:6px 10px; border-radius:8px; border:1px solid #666; background:#1b1b1b; color:#fff;">
      Collapse
    </button>
  </div>
  <pre id="llm-body" style="margin-top:10px; max-height:240px; overflow:auto; white-space:pre-wrap; line-height:1.35; border:0; background:transparent; color:inherit;">__ESCAPED__</pre>
</div>
<script>
(function(){
  var btn = document.getElementById('llm-toggle');
  var body = document.getElementById('llm-body');
  if(!btn || !body) return;
  btn.addEventListener('click', function(){
    var hidden = body.style.display === 'none';
    body.style.display = hidden ? 'block' : 'none';
    btn.textContent = hidden ? 'Collapse' : 'Expand';
  });
})();
</script>
'''.replace('__ESCAPED__', escaped)

Path("llm_block.html").write_text(block, encoding="utf-8")
PY

  awk '
    BEGIN { inserted=0 }
    /^[[:space:]]*<body[^>]*>/ && inserted==0 {
      print
      while ((getline line < "llm_block.html") > 0) print line
      close("llm_block.html")
      inserted=1
      next
    }
    { print }
    END {
      if (inserted==0) {
        print "ERROR: real <body> tag not found at line start; no injection done." > "/dev/stderr"
        exit 1
      }
    }
  ' "${multiqc_html}" > multiqc_report_with_llm.html

  test -s multiqc_report_with_llm.html
  """
}
