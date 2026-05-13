"""
Test to verify the login regression fix: audit_mode defaults to None for normal runtime.

This test checks:
1. In normal mode (AUDIT_MODE not set), the app uses Supabase database_url
2. In local_test mode, the app uses SQLite
3. In supabase_readonly mode, the app uses Supabase via DATABASE_URL env var
"""
import os
import pytest


@pytest.fixture(autouse=True)
def clear_audit_mode():
    """Clear AUDIT_MODE for each test to ensure isolation."""
    old_mode = os.environ.get("AUDIT_MODE")
    # Clear for the test
    if "AUDIT_MODE" in os.environ:
        del os.environ["AUDIT_MODE"]
    yield
    # Restore after test
    if old_mode:
        os.environ["AUDIT_MODE"] = old_mode
    elif "AUDIT_MODE" in os.environ:
        del os.environ["AUDIT_MODE"]


def test_normal_mode_uses_supabase_database_url(clear_audit_mode):
    """In normal mode (AUDIT_MODE not set), app should use database_url from .env (Supabase)."""
    # Ensure AUDIT_MODE is not set
    assert "AUDIT_MODE" not in os.environ
    
    # Import fresh settings to avoid cached values
    from importlib import reload
    import app.core.config as config_module
    reload(config_module)
    settings = config_module.settings
    
    # Verify normal mode
    assert settings.audit_mode is None, "audit_mode should be None when AUDIT_MODE env var not set"
    assert settings.is_normal_mode, "Should be in normal mode"
    assert not settings.is_local_test_mode, "Should not be in local_test mode"
    assert not settings.is_supabase_mode, "Should not be in supabase_readonly mode"
    
    # Verify database configuration
    assert "postgresql" in settings.effective_database_url, \
        f"Normal mode should use Supabase (postgresql), but got: {settings.effective_database_url}"
    assert settings.database_url.startswith("postgresql"), \
        f"database_url should be postgresql from .env, but got: {settings.database_url}"
    
    print(f"✓ Normal mode database: {settings.masked_database_url}")
    print(f"  Dialect: {settings.db_dialect}")


def test_local_test_mode_uses_sqlite(clear_audit_mode):
    """In local_test mode, app should use SQLite."""
    os.environ["AUDIT_MODE"] = "local_test"
    
    # Import fresh settings
    from importlib import reload
    import app.core.config as config_module
    reload(config_module)
    settings = config_module.settings
    
    # Verify local_test mode
    assert settings.audit_mode == "local_test", "audit_mode should be 'local_test'"
    assert not settings.is_normal_mode, "Should not be in normal mode"
    assert settings.is_local_test_mode, "Should be in local_test mode"
    assert not settings.is_supabase_mode, "Should not be in supabase_readonly mode"
    
    # Verify database configuration
    assert "sqlite" in settings.effective_database_url, \
        f"local_test mode should use SQLite, but got: {settings.effective_database_url}"
    assert settings.db_dialect == "sqlite", "Dialect should be sqlite in local_test mode"
    
    print(f"✓ Local test mode database: {settings.masked_database_url}")
    print(f"  Dialect: {settings.db_dialect}")


def test_supabase_readonly_mode(clear_audit_mode):
    """In supabase_readonly mode, app should use Supabase."""
    os.environ["AUDIT_MODE"] = "supabase_readonly"
    
    # Import fresh settings
    from importlib import reload
    import app.core.config as config_module
    reload(config_module)
    settings = config_module.settings
    
    # Verify supabase_readonly mode
    assert settings.audit_mode == "supabase_readonly", "audit_mode should be 'supabase_readonly'"
    assert not settings.is_normal_mode, "Should not be in normal mode"
    assert not settings.is_local_test_mode, "Should not be in local_test mode"
    assert settings.is_supabase_mode, "Should be in supabase_readonly mode"
    
    # Verify database configuration
    assert settings.db_dialect == "postgresql", "Dialect should be postgresql in supabase_readonly mode"
    
    print(f"✓ Supabase readonly mode database: {settings.masked_database_url}")
    print(f"  Dialect: {settings.db_dialect}")


def test_environment_metadata_normal_mode(clear_audit_mode):
    """Verify environment metadata reflects normal mode correctly."""
    assert "AUDIT_MODE" not in os.environ
    
    from importlib import reload
    import app.core.config as config_module
    reload(config_module)
    settings = config_module.settings
    
    metadata = settings.get_environment_metadata()
    assert metadata["audit_mode"] is None
    assert "PostgreSQL" in metadata["database_provider"]
    assert metadata["database_dialect"] == "postgresql"
    assert metadata["read_only_mode"] is False
    
    print(f"✓ Environment metadata: {metadata}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
