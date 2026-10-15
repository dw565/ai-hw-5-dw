"""Keep tests away from the real working DB: every test gets its own copy of the original."""

import shutil

import pytest


@pytest.fixture(autouse=True)
def isolated_working_db(tmp_path, monkeypatch):
    from backend import config

    db = tmp_path / "campus_customs_test.db"
    shutil.copy(config.ORIGINAL_DB, db)
    monkeypatch.setattr(config, "WORKING_DB", db)
    return db
