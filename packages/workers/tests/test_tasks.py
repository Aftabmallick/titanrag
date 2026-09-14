from titan_workers.outbox.reconciler import reconcile_vector_storage
from titan_workers.tasks.housekeeping import cleanup_stale_tasks


def test_housekeeping_task_execution():
    res = cleanup_stale_tasks.apply()
    assert res.status == "SUCCESS"
    assert res.result["status"] == "completed"
    assert "cleaned_tasks" in res.result
    assert "purged_outbox" in res.result


def test_reconciler_task_execution():
    res = reconcile_vector_storage.apply()
    assert res.status == "SUCCESS"
    assert res.result["status"] == "success"
    assert "orphans_detected" in res.result
    assert "tombstones_purged" in res.result
