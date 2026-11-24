"""Toolkit bundling the CrowdWisdom Trading tools."""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, BaseToolkit
from pydantic import ConfigDict, Field

from langchain_crowdwisdom.tools import (
    CrowdWisdomSentimentToday,
    CrowdWisdomSentimentWeek,
    _free_client,
)


class CrowdWisdomToolkit(BaseToolkit):
    """CrowdWisdom Trading toolkit: daily and weekly crowd sentiment tools.

    Setup:
        .. code-block:: bash

            pip install -U langchain-crowdwisdom

    Instantiate:
        .. code-block:: python

            from langchain_crowdwisdom import CrowdWisdomToolkit

            toolkit = CrowdWisdomToolkit()
            tools = toolkit.get_tools()
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    client: Any = Field(default=None, exclude=True)
    """A shared ``crowdwisdomtrading.Client``. Built with free settings when not given."""

    def get_tools(self) -> list[BaseTool]:
        client = self.client if self.client is not None else _free_client()
        return [
            CrowdWisdomSentimentToday(client=client),
            CrowdWisdomSentimentWeek(client=client),
        ]
