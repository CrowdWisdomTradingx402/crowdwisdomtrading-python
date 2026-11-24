from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

from tools import client


class CrowdWisdomTool(Tool):
    cycle = "daily"
    period = "today"

    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage, None, None]:
        try:
            payload = client.get_sentiment(tool_parameters.get("ticker"), self.cycle)
        except client.CrowdWisdomError as exc:
            yield self.create_text_message(str(exc))
            return
        yield self.create_text_message(client.summarize(payload, self.period))
        yield self.create_json_message(payload)
