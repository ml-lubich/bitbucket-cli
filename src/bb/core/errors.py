from __future__ import annotations


class BBError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)


class AuthError(BBError):
    pass


class ApiError(BBError):
    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.status = status_code  # compat alias
        super().__init__(f"API {status_code}: {message}")


class ContextError(BBError):
    pass


class ConfigError(BBError):
    pass
