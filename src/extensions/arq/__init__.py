"""ARQ integration helpers for background jobs."""

from src.extensions.arq.middleware import arq_job_middleware


def __getattr__(name: str):
    if name == "WorkerSettings":
        from src.extensions.arq.arq_common import WorkerSettings

        return WorkerSettings
    raise AttributeError(name)


__all__ = ["WorkerSettings", "arq_job_middleware"]
