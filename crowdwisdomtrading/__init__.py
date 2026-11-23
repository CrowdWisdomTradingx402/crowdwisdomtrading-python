"""crowdwisdomtrading: client for CrowdWisdom Trading crowd data (free weekly crowd score, x402 pay-per-call or Bearer key)."""
from crowdwisdomtrading.client import Client, CrowdWisdomError, PaymentFailed

__version__ = "0.2.3"
__all__ = ["Client", "CrowdWisdomError", "PaymentFailed", "__version__"]
