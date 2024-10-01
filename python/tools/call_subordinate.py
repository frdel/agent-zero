from typing import Any, Optional
from python.helpers.tool import Tool, Response


class Delegation(Tool):
    async def execute(
        self, message: str = "", reset: str = "", **kwargs: Any
    ) -> Response:
        subordinate: Optional[Any] = self.get_agent_data(self.agent, "subordinate")

        if subordinate is None or str(reset).lower().strip() == "true":
            try:
                Agent = getattr(self.agent, "__class__")
                subordinate = Agent(self.agent.number + 1, self.agent.config)

                self.set_agent_data(self.agent, "subordinate", subordinate)
                self.set_agent_data(subordinate, "superior", self.agent)
            except Exception as e:
                print(f"Error creating subordinate agent: {e}")
                return Response(
                    message="Failed to create subordinate agent", break_loop=False
                )

        if subordinate is None:
            return Response(message="No subordinate agent available", break_loop=False)

        try:
            message_loop = getattr(subordinate, "message_loop", None)
            generate_response = getattr(subordinate, "generate_response", None)

            if callable(message_loop):
                response = await message_loop(message)
            elif callable(generate_response):
                response = await generate_response(message)
            else:
                raise AttributeError(
                    "Subordinate agent has no message_loop or generate_response method"
                )
            return Response(message=response, break_loop=False)
        except Exception as e:
            print(f"Error in subordinate agent processing: {e}")
            return Response(
                message=f"Error occurred in subordinate agent: {str(e)}",
                break_loop=False,
            )

    def set_agent_data(self, agent: Any, key: str, value: Any) -> None:
        set_data = getattr(agent, "set_data", None)
        if callable(set_data):
            set_data(key, value)
        elif hasattr(agent, "data"):
            agent.data[key] = value
        else:
            print(f"Warning: Unable to set data '{key}' on agent")

    def get_agent_data(self, agent: Any, key: str) -> Any:
        get_data = getattr(agent, "get_data", None)
        if callable(get_data):
            return get_data(key)
        elif hasattr(agent, "data"):
            return agent.data.get(key)
        else:
            print(f"Warning: Unable to get data '{key}' from agent")
            return None

    def before_execution(self, **kwargs):
        # Implement any pre-execution logic here if needed
        pass

    def after_execution(self, response: Response, **kwargs):
        # Implement any post-execution logic here if needed
        pass
