class MagentaTvException(Exception):
    """Exceptions related to the MagentaTV client"""


class CommunicationException(MagentaTvException):
    """Error to indicate that platform is not ready."""


class CommunicationTimeoutException(CommunicationException):
    """Error to indicate that platform is not ready."""


class PairingTimeoutException(MagentaTvException):
    """Error to indicate that platform is not ready."""


class NotPairedException(MagentaTvException):
    """Error to indicate that platform is not ready for the requested resource."""
