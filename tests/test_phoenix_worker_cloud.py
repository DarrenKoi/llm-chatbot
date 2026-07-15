"""Office-cloud Phoenix storage checks.

Run explicitly in the office with a confirmed persistent local path:

    PHOENIX_OFFICE_TEST_DIR=/project/workSpace/phoenix-data \
        pytest tests/test_phoenix_worker_cloud.py -v
"""

import os
from pathlib import Path

import pytest

import phoenix_worker

OFFICE_TEST_DIRECTORY = os.environ.get("PHOENIX_OFFICE_TEST_DIR", "").strip()


@pytest.mark.skipif(
    not OFFICE_TEST_DIRECTORY,
    reason="PHOENIX_OFFICE_TEST_DIR is not configured for an office-cloud storage check",
)
def test_office_phoenix_directory_is_persistent_volume_candidate(monkeypatch):
    """The confirmed office path can be created and written by the daemon user."""

    working_directory = Path(OFFICE_TEST_DIRECTORY)
    monkeypatch.setenv("PHOENIX_WORKING_DIR", str(working_directory))
    monkeypatch.delenv("PHOENIX_SQL_DATABASE_URL", raising=False)

    resolved = phoenix_worker.prepare_sqlite_storage()

    assert resolved == working_directory.resolve()
    assert working_directory.is_dir()
    assert os.environ["PHOENIX_SQL_DATABASE_URL"].endswith("/phoenix.db")
