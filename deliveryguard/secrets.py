"""Resolve secrets by reference without placing values in configuration."""

from __future__ import annotations

import os
import re

ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]{1,127}$")


class SecretResolutionError(ValueError):
    pass


class EnvironmentSecretResolver:
    def resolve(self, reference: str) -> str:
        if not reference.startswith("env:"):
            raise SecretResolutionError("Only env: secret references are supported.")
        name = reference.removeprefix("env:")
        if not ENV_NAME.fullmatch(name):
            raise SecretResolutionError(
                "Secret reference contains an invalid environment name."
            )
        value = os.environ.get(name)
        if not value:
            raise SecretResolutionError(
                f"Required secret reference env:{name} is unavailable."
            )
        return value
