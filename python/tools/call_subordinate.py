from agent import Agent
from python.helpers.tool import Tool, Response

class Delegation(Tool):

    def execute(self, message="", agent_name="", reset="", **kwargs):
        # Check if we need to create a new subordinate or reset the existing one
        if self.agent.get_data("subordinate") is None or str(reset).lower().strip() == "true":
            # Extract the current agent's number
            current_number = self.agent.number  # Use the existing number directly
            
            # Determine the new subordinate's number
            new_number = current_number + 1
            
            # Check if we've reached the delegation limit
            max_delegation = 5  # You can adjust this number as needed
            if new_number > max_delegation:
                return Response(
                    message="Maximum delegation depth reached. Cannot create more subordinates.",
                    break_loop=True
                )
            
            # Create the new subordinate agent with the correct number
            subordinate = Agent(new_number, self.agent.config)
            subordinate.set_data("superior", self.agent)
            self.agent.set_data("subordinate", subordinate)
        
        # Get the existing subordinate
        subordinate = self.agent.get_data("subordinate")
        
        # Delegate the task to the subordinate
        response = subordinate.message_loop(message)
        
        return Response(message=response, break_loop=False)
