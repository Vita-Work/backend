from __future__ import annotations

from src.services.job_parsers.base import BaseJobParser

_PARSER_CLASSES: dict[str, type[BaseJobParser]] = {}
_INSTANCES: dict[str, BaseJobParser] = {}


def register_parser(name: str):
    def wrapper(cls: type[BaseJobParser]):
        _PARSER_CLASSES[name] = cls
        return cls

    return wrapper


def get_parser(name: str) -> BaseJobParser:
    if name not in _INSTANCES:
        if name not in _PARSER_CLASSES:
            raise ValueError(f"Job parser '{name}' is not registered.")
        _INSTANCES[name] = _PARSER_CLASSES[name]()
    return _INSTANCES[name]


def get_registered_parser_names() -> list[str]:
    return sorted(_PARSER_CLASSES.keys())
