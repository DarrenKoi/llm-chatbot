from datetime import date

from api.utils.scheduler.tasks import cleanup as cleanup_task


def test_cleanup_uwsgi_logs_deletes_only_files_older_than_a_week_by_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(cleanup_task.config, "LOG_DIR", tmp_path)

    old_log = tmp_path / "uwsgi-2026-02-24.log"  # 8 days old from 2026-03-04
    boundary_log = tmp_path / "uwsgi-2026-02-25.log"  # exactly 7 days old
    recent_log = tmp_path / "uwsgi-2026-03-03.log"
    typo_prefix_old_log = tmp_path / "uwsi-2026-02-24.log"
    invalid_date_log = tmp_path / "uwsgi-2026-02-30.log"
    unrelated_log = tmp_path / "app.log"

    for path in (old_log, boundary_log, recent_log, typo_prefix_old_log, invalid_date_log, unrelated_log):
        path.write_text("x", encoding="utf-8")

    cleanup_task._cleanup_uwsgi_logs(today=date(2026, 3, 4))

    assert not old_log.exists()
    assert boundary_log.exists()
    assert recent_log.exists()
    assert not typo_prefix_old_log.exists()
    assert invalid_date_log.exists()
    assert unrelated_log.exists()
