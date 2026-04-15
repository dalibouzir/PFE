class AppError(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class NotFoundError(AppError):
    def __init__(self, detail: str):
        super().__init__(404, detail)


class ConflictError(AppError):
    def __init__(self, detail: str):
        super().__init__(409, detail)


class ForbiddenError(AppError):
    def __init__(self, detail: str):
        super().__init__(403, detail)


class AuthenticationError(AppError):
    def __init__(self, detail: str = "Invalid authentication credentials."):
        super().__init__(401, detail)


class ValidationError(AppError):
    def __init__(self, detail: str):
        super().__init__(422, detail)
