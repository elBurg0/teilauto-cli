from __future__ import annotations


class TeilautoError(Exception):
    """Base error; the CLI root handler renders message + hint and exits with exit_code."""

    exit_code = 1

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.hint = hint


class ApiError(TeilautoError):
    pass


class RateLimitedError(ApiError):
    pass


class AuthRequiredError(TeilautoError):
    exit_code = 3

    def __init__(self, message: str = "Not logged in or token expired.") -> None:
        super().__init__(message, hint="Run `teilauto auth login` to authenticate.")


class NotFoundError(TeilautoError):
    exit_code = 4


class ConfigError(TeilautoError):
    pass


class NoMatchError(TeilautoError):
    exit_code = 2
