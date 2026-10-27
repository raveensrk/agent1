"""Adapter registry for agent-usage-report.

An adapter is a module in this package exposing:

    NAME            str, stable harness id
    LABEL           str, human name
    available()     bool, whether any log root exists on this machine
    discover()      list of existing root paths
    records()       iterator of normalised records (see util.make)

Order matters only for display. Unknown harnesses can be added by dropping a
new module in this directory and adding its name to ``_MODULES``; the
``generic_jsonl`` adapter covers anything declared in the user config.
"""

from __future__ import annotations

import importlib

_MODULES = ("pi", "claude_code", "codex", "opencode", "opencode_zen", "generic_jsonl")


def load(name, config=None):
    """Import one adapter, injecting config for those that need it."""
    module = importlib.import_module("adapters." + name)
    if config is not None and hasattr(module, "configure"):
        module.configure(config)
    return module


def all_adapters(config=None):
    """Every adapter that imports cleanly, in registry order."""
    modules = []
    for name in _MODULES:
        try:
            modules.append(load(name, config))
        except Exception:
            continue
    return modules
