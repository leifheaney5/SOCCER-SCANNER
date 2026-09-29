#!/usr/bin/env bash
set -uo pipefail

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$root_dir"

if [[ -n "${VIRTUAL_ENV:-}" ]] && command -v python >/dev/null 2>&1; then
    python_cmd='python'
elif [[ -x .venv/Scripts/python.exe ]]; then
    python_cmd='.venv/Scripts/python.exe'
elif [[ -x .venv/bin/python ]]; then
    python_cmd='.venv/bin/python'
elif command -v py >/dev/null 2>&1; then
    python_cmd='py -3'
elif command -v python3 >/dev/null 2>&1; then
    python_cmd='python3'
elif command -v python >/dev/null 2>&1; then
    python_cmd='python'
else
    printf 'Python 3 is required for the repository checks.\n' >&2
    exit 127
fi

usage() {
    printf 'Usage: ./check.sh <T001..T009|all> [--mark]\n'
}

task_id="${1:-}"
mark="${2:-}"
if (( $# > 2 )) || [[ -z "$task_id" || ( -n "$mark" && "$mark" != "--mark" ) ]]; then
    usage >&2
    exit 2
fi
if [[ "$mark" == "--mark" && "$task_id" == "all" ]]; then
    printf 'Mark one task at a time; aggregate runs cannot update the ledger.\n' >&2
    exit 2
fi

run_check() {
    local id="$1"
    local command="$2"
    local timestamp log status
    timestamp="$(date -u +%Y%m%d-%H%M%S)"
    mkdir -p .checks/logs
    log=".checks/logs/${id}-${timestamp}.log"
    printf 'COMMAND: %s\n' "$command" | tee "$log"
    bash -o pipefail -c "$command" 2>&1 | tee -a "$log"
    status=${PIPESTATUS[0]}
    if (( status == 0 )); then
        printf 'RESULT: PASS\n' | tee -a "$log"
    else
        printf 'RESULT: FAIL\n' | tee -a "$log"
    fi
    printf 'EXIT: %s\nLOG: %s\n' "$status" "$log" | tee -a "$log"
    return "$status"
}

mark_task() {
    $python_cmd - "$1" <<'PY'
from pathlib import Path
import sys

task_id = sys.argv[1]
ledger = Path('todo.md')
text = ledger.read_text(encoding='utf-8')
old = f'- [ ] {task_id}:'
new = f'- [x] {task_id}:'
if text.count(old) == 1 and new not in text:
    ledger.write_text(text.replace(old, new, 1), encoding='utf-8')
    print(f'Marked {task_id} after its check passed.')
elif text.count(new) == 1 and old not in text:
    print(f'{task_id} is already marked complete.')
else:
    raise SystemExit(f'Expected exactly one unchecked ledger row for {task_id}.')
PY
}

run_task() {
    local id="$1"
    local command status
    case "$id" in
        T001) command='npx playwright test --project=chromium --project=webkit' ;;
        T002) command="PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $python_cmd -m pytest tests/test_public_routes.py tests/test_app.py -q" ;;
        T003) command='npx playwright test tests/browser/branding.spec.js tests/browser/pwa.spec.js --project=chromium --project=webkit' ;;
        T004) command="PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $python_cmd -m pytest tests/test_ios_release_assets.py -q && gh run list --commit c7116a5eeb0f9a39f9859ff873e754b6e6eab1bf --json workflowName,status,conclusion,headSha | $python_cmd -c 'import json,sys; runs=json.load(sys.stdin); sha=\"c7116a5eeb0f9a39f9859ff873e754b6e6eab1bf\"; required={\"CI\",\"iOS\"}; good={r[\"workflowName\"] for r in runs if r[\"headSha\"]==sha and r[\"status\"]==\"completed\" and r[\"conclusion\"]==\"success\"}; missing=required-good; print(\"Exact-SHA hosted workflows: \"+\", \".join(sorted(required-missing))); sys.exit(bool(missing))'" ;;
        T005) command='node --test tests/synthetic-monitor.test.mjs' ;;
        T006) command="BASE_URL=https://soccer-radar.com EXPECTED_SHA=c7116a5eeb0f9a39f9859ff873e754b6e6eab1bf EXPECTED_ENVIRONMENT=production npm run smoke:production && node --input-type=module -e 'const origin=\"https://soccerscanner.pro\"; const target=\"https://soccer-radar.com\"; const path=\"/fixtures/legacy-cleanup-check?date=2026-09-29&timezone=America%2FNew_York\"; const response=await fetch(origin+path,{redirect:\"manual\"}); const location=response.headers.get(\"location\"); if(![301,302,307,308].includes(response.status)||!location) throw new Error(\`Expected legacy redirect, got \${response.status}\`); const redirected=new URL(location,origin); if(redirected.origin!==target||redirected.pathname!==path.split(\"?\")[0]||redirected.search!==\"?date=2026-09-29&timezone=America%2FNew_York\") throw new Error(\`Unexpected redirect: \${location}\`); console.log(\`Legacy redirect: \${response.status} \${origin+path} -> \${location}\`);' && gh run list --commit c7116a5eeb0f9a39f9859ff873e754b6e6eab1bf --json workflowName,status,conclusion,headSha | $python_cmd -c 'import json,sys; runs=json.load(sys.stdin); sha=\"c7116a5eeb0f9a39f9859ff873e754b6e6eab1bf\"; required={\"CI\",\"iOS\"}; good={r[\"workflowName\"] for r in runs if r[\"headSha\"]==sha and r[\"status\"]==\"completed\" and r[\"conclusion\"]==\"success\"}; missing=required-good; print(\"Exact-SHA hosted workflows: \"+\", \".join(sorted(required-missing))); sys.exit(bool(missing))'" ;;
        T007) command="PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $python_cmd -m pytest tests/test_espn_provider.py tests/test_streaming_registry.py tests/test_fixture_service_v2.py tests/test_streaming_enrichment.py tests/test_ios_release_assets.py -q && npx playwright test tests/browser/streaming.spec.js tests/browser/pwa.spec.js --project=chromium --project=webkit && gh run list --commit c7116a5eeb0f9a39f9859ff873e754b6e6eab1bf --json workflowName,status,conclusion,headSha | $python_cmd -c 'import json,sys; runs=json.load(sys.stdin); sha=\"c7116a5eeb0f9a39f9859ff873e754b6e6eab1bf\"; required={\"iOS\"}; good={r[\"workflowName\"] for r in runs if r[\"headSha\"]==sha and r[\"status\"]==\"completed\" and r[\"conclusion\"]==\"success\"}; missing=required-good; print(\"Exact-SHA hosted workflows: \"+\", \".join(sorted(required-missing))); sys.exit(bool(missing))'" ;;
        T008) command="bash -n check.sh && PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 $python_cmd -m pytest tests/test_docs_contract.py -q && git diff --check" ;;
        T009)
            if [[ ! -f LICENSE ]]; then
                command='printf "LICENSE is pending the exact copyright-holder name; no placeholder rights holder will be written.\\n"; exit 1'
            else
                command="$python_cmd tests/verify_license_provenance.py"
            fi
            ;;
        *) printf 'Unknown task ID: %s\n' "$id" >&2; return 2 ;;
    esac

    run_check "$id" "$command"
    status=$?
    if (( status != 0 )); then
        return "$status"
    fi
    if [[ "$mark" == "--mark" ]]; then
        mark_task "$id"
    fi
}

if [[ "$task_id" == "all" ]]; then
    result=0
    for id in T001 T002 T003 T004 T005 T006 T007 T008 T009; do
        if ! run_task "$id"; then result=1; fi
    done
    exit "$result"
fi

run_task "$task_id"
