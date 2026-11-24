from typing import Any

from dify_plugin import ToolProvider


class CrowdWisdomProvider(ToolProvider):
    def _validate_credentials(self, credentials: dict[str, Any]) -> None:
        # The free endpoints need no API key, so there is nothing to validate.
        return None
