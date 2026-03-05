class ContextRequiredError(RuntimeError):
    def __init__(
        self, message="This operation must be performed within a context manager."
    ):
        super().__init__(message)
