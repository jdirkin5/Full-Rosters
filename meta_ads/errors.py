class MetaAdsError(Exception):
    """Base class for tool errors."""


class ConfigError(MetaAdsError):
    pass


class ApiError(MetaAdsError):
    def __init__(self, status: int, code: int | None, subcode: int | None,
                 message: str, user_msg: str | None = None, trace: str | None = None):
        self.status = status
        self.code = code
        self.subcode = subcode
        self.message = message
        self.user_msg = user_msg
        self.trace = trace
        super().__init__(self.__str__())

    def __str__(self) -> str:
        parts = [f"Meta API error {self.status}"]
        if self.code is not None:
            parts.append(f"code={self.code}")
        if self.subcode is not None:
            parts.append(f"subcode={self.subcode}")
        s = " ".join(parts) + f": {self.message}"
        if self.user_msg:
            s += f" | {self.user_msg}"
        if self.trace:
            s += f" (fbtrace_id={self.trace})"
        return s


class GuardrailError(MetaAdsError):
    """A safety rule refused the operation outright."""


class ApprovalRequired(MetaAdsError):
    """The operation needs an explicit human approval id."""

    def __init__(self, approval_id: str, summary: str):
        self.approval_id = approval_id
        self.summary = summary
        super().__init__(
            f"APPROVAL REQUIRED [{approval_id}]\n{summary}\n"
            f"Ask the human to approve, then re-run with --approve {approval_id}"
        )
