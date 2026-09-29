import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_doc(path):
    return (ROOT / path).read_text(encoding='utf-8')


def test_production_smoke_defaults_to_canonical_domain_and_documents_legacy_redirect():
    testing = read_doc('docs/testing.md')

    assert "$env:BASE_URL='https://soccer-radar.com'" in testing
    assert 'https://soccerscanner.pro' in testing
    assert 'same path and query' in testing


def test_watch_option_schema_matches_serialized_fields_and_additive_semantics():
    schema = read_doc('openapi/soccer-scanner-v2.yaml')
    api = read_doc('docs/api.md')

    assert "items: {$ref: '#/components/schemas/WatchOption'}" in schema
    for field in (
        'id, displayName, officialUrl, region, regionKnown, type, source, '
        'sourceId, observedAt'
    ).split(', '):
        assert f'{field}:' in schema
        assert f'`{field}`' in api
    assert '`logoPath` is optional' in api
    assert 'an empty list means no supported TV or streaming entries were' in api
    assert 'responses when enrichment is disabled' in api
    assert 'The legacy `streaming` array remains streaming-only' in api


def test_current_docs_use_soccer_radar_and_changelog_has_one_unreleased_section():
    current_docs = (
        'docs/README.md',
        'docs/analytics.md',
        'docs/data-sources.md',
        'docs/free-broadcast-coverage.md',
        'docs/provider-capabilities.md',
        'docs/seo.md',
    )
    for path in current_docs:
        assert 'Soccer Radar' in read_doc(path), path

    railway = read_doc('docs/railway-architecture.md')
    assert 'Production serves `soccer-radar.com`' in railway
    assert 'redirects them to the matching canonical route' in railway

    changelog = read_doc('CHANGELOG.md')
    assert changelog.count('## Unreleased') == 1
    assert '## Unreleased -' not in changelog


def test_readme_explains_the_task_check_runner_and_mark_safeguard():
    readme = read_doc('README.md')

    assert 'bash ./check.sh T###' in readme
    assert '.checks/logs/' in readme
    assert 'only to mark a task whose check passes' in readme

    ledger = read_doc('todo.md')
    task_ids = re.findall(r'^- \[[ x]\] (T\d{3}):', ledger, flags=re.MULTILINE)
    assert task_ids == [f'T{number:03d}' for number in range(1, 10)]
    for task_id in task_ids:
        task = re.search(
            rf'^- \[[ x]\] {task_id}:.*?(?=^- \[[ x]\] T\d{{3}}:|\Z)',
            ledger,
            flags=re.MULTILINE | re.DOTALL,
        )
        assert task is not None
        assert f'Verify: `./check.sh {task_id}`' in task.group()
