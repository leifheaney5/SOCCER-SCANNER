from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_active_product_docs_describe_guest_mode_without_persistent_favorites():
    active_docs = [
        ROOT / 'README.md',
        ROOT / 'docs' / 'architecture.md',
        ROOT / 'docs' / 'api.md',
        ROOT / 'docs' / 'testing.md',
        ROOT / 'docs' / 'data-sources.md',
        ROOT / 'docs' / 'deployment.md',
        ROOT / 'clients' / 'ios' / 'README.md',
    ]
    text = '\n'.join(path.read_text(encoding='utf-8').lower() for path in active_docs)
    assert 'favorites stay in browser `localstorage`' not in text
    assert 'favorites stay in localstorage' not in text
    assert 'persistent score preference' not in text
    assert 'no accounts' in text or 'no account' in text
    assert 'persistent favorites' in text
    assert 'cross-device synchronization' in text
