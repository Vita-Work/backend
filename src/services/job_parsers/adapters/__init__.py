import importlib

from src.logger import get_logger
from src.services.job_parsers.adapters import computrabajo, devkg, getonbrd, habr_career, hh

logger = get_logger("services.job_parsers.adapters")

__all__ = ["devkg", "habr_career", "computrabajo", "getonbrd", "hh"]

try:
    importlib.import_module("src.services.job_parsers.adapters.indeed")
except ModuleNotFoundError as exc:
    logger.warning(
        "job_parser_adapter_optional_dependency_missing",
        adapter="indeed",
        error=str(exc),
    )
else:
    __all__.append("indeed")
