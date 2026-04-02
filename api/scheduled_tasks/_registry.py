import importlib
import inspect
import logging
import pkgutil
from typing import Any, Callable

from api.scheduled_tasks._lock import run_locked_job

logger = logging.getLogger(__name__)

_TASK_META_ATTR = "__scheduler_task_meta__"

__all__ = ["discover_and_register", "scheduled_job"]


def scheduled_job(
    *,
    id: str,
    use_distributed_lock: bool = True,
    lock_id: str | None = None,
    **trigger_kwargs: Any,
):
    """Decorator to declare a scheduler job without register(scheduler)."""

    def _decorator(func: Callable[[], None]) -> Callable[[], None]:
        setattr(
            func,
            _TASK_META_ATTR,
            {
                "id": id,
                "use_distributed_lock": use_distributed_lock,
                "lock_id": lock_id or id,
                "trigger_kwargs": trigger_kwargs,
            },
        )
        return func

    return _decorator


def _iter_decorated_jobs(module) -> list[tuple[Callable[[], None], dict[str, Any]]]:
    jobs: list[tuple[Callable[[], None], dict[str, Any]]] = []
    for _, obj in inspect.getmembers(module):
        meta = getattr(obj, _TASK_META_ATTR, None)
        if meta is None:
            continue
        if not callable(obj):
            logger.warning("Invalid scheduler task in '%s': decorated target is not callable.", module.__name__)
            continue
        jobs.append((obj, meta))
    return jobs


def _build_job_callable(job_func: Callable[[], None], lock_id: str, use_distributed_lock: bool) -> Callable[[], None]:
    if not use_distributed_lock:
        return job_func

    def _locked() -> None:
        run_locked_job(lock_id, job_func)

    return _locked


def _register_decorated_jobs(scheduler, module) -> int:
    registered = 0
    jobs = _iter_decorated_jobs(module)
    for job_func, meta in jobs:
        scheduler.add_job(
            _build_job_callable(job_func, lock_id=meta["lock_id"], use_distributed_lock=meta["use_distributed_lock"]),
            id=meta["id"],
            replace_existing=True,
            **meta["trigger_kwargs"],
        )
        registered += 1
    return registered


def _scan_package(scheduler, package) -> None:
    for module_info in pkgutil.iter_modules(package.__path__, package.__name__ + "."):
        short_name = module_info.name.rsplit(".", 1)[-1]
        if short_name.startswith("_"):
            continue

        try:
            mod = importlib.import_module(module_info.name)
        except Exception:
            logger.exception("Failed to import scheduler task module: %s", module_info.name)
            continue

        register_fn = getattr(mod, "register", None)

        used_legacy_register = False
        if callable(register_fn):
            try:
                register_fn(scheduler)
                used_legacy_register = True
                logger.info("Registered scheduler tasks from '%s' via register().", module_info.name)
            except Exception:
                logger.exception("Failed to register scheduler tasks from '%s' via register().", module_info.name)

        decorated_count = 0
        try:
            decorated_count = _register_decorated_jobs(scheduler, mod)
            if decorated_count > 0:
                logger.info(
                    "Registered %s scheduler task(s) from '%s' via @scheduled_job.",
                    decorated_count,
                    module_info.name,
                )
        except Exception:
            logger.exception("Failed to register scheduler tasks from '%s' via @scheduled_job.", module_info.name)

        if not used_legacy_register and decorated_count == 0:
            logger.warning(
                "Scheduler task module '%s' has no register() or @scheduled_job task, skipping.",
                module_info.name,
            )


def _register_task_package(scheduler, package_path: str) -> None:
    task_mod_name = f"{package_path}.task"
    try:
        mod = importlib.import_module(task_mod_name)
    except Exception:
        logger.exception("Failed to import task module: %s", task_mod_name)
        return

    register_fn = getattr(mod, "register", None)
    if callable(register_fn):
        try:
            register_fn(scheduler)
            logger.info("Registered scheduler tasks from '%s' via register().", task_mod_name)
        except Exception:
            logger.exception("Failed to register scheduler tasks from '%s' via register().", task_mod_name)

    try:
        count = _register_decorated_jobs(scheduler, mod)
        if count > 0:
            logger.info("Registered %s scheduler task(s) from '%s' via @scheduled_job.", count, task_mod_name)
    except Exception:
        logger.exception("Failed to register scheduler tasks from '%s' via @scheduled_job.", task_mod_name)


_TASK_PACKAGES = [
    "api.scheduled_tasks.scan_member_info",
]


def discover_and_register(scheduler) -> None:
    from api.scheduled_tasks import tasks

    _scan_package(scheduler, tasks)

    for pkg_path in _TASK_PACKAGES:
        _register_task_package(scheduler, pkg_path)
