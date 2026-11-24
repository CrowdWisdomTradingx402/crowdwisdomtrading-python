from tools import base


class SentimentTodayTool(base.CrowdWisdomTool):
    cycle = "daily"
    period = "today"
