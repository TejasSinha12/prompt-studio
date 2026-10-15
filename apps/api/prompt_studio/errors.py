"""Application errors mapped to consistent JSON responses."""

from __future__ import annotations


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or {}


def not_found(what: str) -> AppError:
    return AppError(404, "not_found", f"{what} not found.")


def conflict(message: str, **details) -> AppError:
    return AppError(409, "conflict", message, details)


def bad_request(message: str, code: str = "bad_request") -> AppError:
    return AppError(400, code, message)
