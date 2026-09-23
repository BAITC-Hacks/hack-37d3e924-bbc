class PipelineError(RuntimeError):
    """Safe error for the application worker; no meeting text or internal paths."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)
