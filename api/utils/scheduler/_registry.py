import importlib
import logging
import pkgutil

logger = logging.getLogger(__name__)


def discover_and_register(scheduler) -> None:
    from api.utils.scheduler import tasks

    for module_info in pkgutil.iter_modules(tasks.__path__, tasks.__name__ + "."):
        short_name = module_info.name.rsplit(".", 1)[-1]
        if short_name.startswith("_"):
            continue

        try:
            mod = importlib.import_module(module_info.name)
        except Exception:
            logger.exception("Failed to import scheduler task module: %s", module_info.name)
            continue

        register_fn = getattr(mod, "register", None)
        if register_fn is None:
            logger.warning("Scheduler task module '%s' has no register() function, skipping.", module_info.name)
            continue

        try:
            register_fn(scheduler)
            logger.info("Registered scheduler tasks from '%s'.", module_info.name)
        except Exception:
            logger.exception("Failed to register scheduler tasks from '%s'.", module_info.name)
