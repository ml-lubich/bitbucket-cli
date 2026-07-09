from __future__ import annotations


class BBError(Exception):
    def __init__(self, message: str, exit_code: int = 1) -> None:
        self.message = message
        self.exit_code = exit_code
        super().__init__(message)


class AuthError(BBError):
    pass


class ApiError(BBError):
    def __init__(
        self,
        status_code: int,
        message: str,
        method: str = "",
        path: str = "",
        hint: str = "",
    ) -> None:
        self.status_code = status_code
        self.status = status_code  # compat alias
        self.method = method
        self.path = path
        self.hint = hint
        details = f"API {status_code}: {message}"
        if method and path:
            details = f"{details} ({method} {path})"
        if hint:
            details = f"{details}. Hint: {hint}"
        super().__init__(details)


class ContextError(BBError):
    pass


class ConfigError(BBError):
    pass
