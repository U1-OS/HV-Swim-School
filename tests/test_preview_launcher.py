"""The demo launcher must not inherit production data or financial credentials."""
import importlib.util
from pathlib import Path


def test_preview_excludes_inherited_production_configuration():
    path = Path(__file__).resolve().parents[1] / 'scripts' / 'preview-local.py'
    spec = importlib.util.spec_from_file_location('preview_local', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env = module.preview_environment({
        'PATH': '/usr/bin', 'HOME': '/example', 'HV_APP_ENV': 'production',
        'HV_LOAD_DOTENV': 'true', 'HV_DATA_DIR': '/business/records',
        'HV_SESSION_SECRET': 'test-secret', 'XERO_SYNC_ENABLED': 'true',
        'XERO_CLIENT_SECRET': 'test-secret', 'HV_SMTP_PASSWORD': 'test-secret',
        'SHOPIFY_STOREFRONT_TOKEN': 'test-secret', 'DATABASE_URL': 'postgres://example',
    })
    assert env['HV_APP_ENV'] == 'development'
    assert env['HV_LOAD_DOTENV'] == 'false'
    assert env['XERO_SYNC_ENABLED'] == 'false'
    assert env['HV_DATA_DIR'] != '/business/records'
    assert env['HV_PUBLIC_URL'] == 'http://127.0.0.1:8772'
    assert not any(key in env for key in ('XERO_CLIENT_SECRET','HV_SMTP_PASSWORD','SHOPIFY_STOREFRONT_TOKEN','DATABASE_URL','HV_SESSION_SECRET'))
    assert env['PATH'] == '/usr/bin'
