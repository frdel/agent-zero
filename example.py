from a2h import A2HRequest, A2HResponse, ResponseType, create_a2h_response
from a2h_tools import request_human_approval, process_human_response

def agent_action():
    """Simulates an agent performing an action and requiring human approval."""
    request = request_human_approval(
        intent="Design a landing page for a fitness app.",
        justification="I have created a draft, but I’m 70% confident about the header section layout.",
        confidence_score=0.7,
        approval_request="Please review the attached design.",
    )
    print(f"Agent: {request.approvalRequest} (Trace ID: {request.traceId})")
    return request

def human_interaction(request: A2HRequest) -> A2HResponse:
    """Simulates a human reviewing the agent's request and providing a response."""
    print("Human: Please choose an action (approve/reject/modify/defer):")
    action = input().lower()
    response_type = ResponseType(action)

    payload = None
    if response_type == ResponseType.MODIFY:
        print("Human: Please provide your modifications:")
        modifications = input()
        payload = {"modifications": modifications}

    return create_a2h_response(request.traceId, response_type, payload)

def main():
    """Main function to run the example."""
    request = agent_action()
    response = human_interaction(request)
    response_type, payload = process_human_response(response)

    print(f"Agent received response: {response_type.value}")
    if payload:
        print(f"Payload: {payload}")


if __name__ == "__main__":
    main()
