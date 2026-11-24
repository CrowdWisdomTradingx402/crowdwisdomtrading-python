"""LangChain integration for CrowdWisdom Trading crowd sentiment."""

from importlib import metadata

from langchain_crowdwisdom.toolkits import CrowdWisdomToolkit
from langchain_crowdwisdom.tools import (
    CrowdWisdomSentimentInput,
    CrowdWisdomSentimentToday,
    CrowdWisdomSentimentWeek,
)

try:
    __version__ = metadata.version(__package__)
except metadata.PackageNotFoundError:
    __version__ = ""
del metadata

__all__ = [
    "CrowdWisdomSentimentInput",
    "CrowdWisdomSentimentToday",
    "CrowdWisdomSentimentWeek",
    "CrowdWisdomToolkit",
    "__version__",
]
