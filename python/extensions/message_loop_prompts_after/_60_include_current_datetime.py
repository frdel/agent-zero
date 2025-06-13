from datetime import datetime, timezone
from python.helpers.extension import Extension
from agent import LoopData
from python.helpers.localization import Localization


class IncludeCurrentDatetime(Extension):
    async def execute(self, loop_data: LoopData = LoopData(), **kwargs):
        # get current datetime
        current_datetime = Localization.get().utc_dt_to_localtime_str(
            datetime.now(timezone.utc), sep=" ", timespec="seconds"
        )
        # remove timezone offset
        if current_datetime and "+" in current_datetime:
            current_datetime = current_datetime.split("+")[0]

        # read prompt
        datetime_prompt = self.agent.read_prompt(
            "agent.system.datetime.md", date_time=current_datetime
        )

        # add current datetime to the loop data
        loop_data.extras_temporary["current_datetime"] = datetime_prompt
