from a2h import A2HRequest, A2HResponse, ResponseType, create_a2h_request

def request_human_approval(intent: str, justification: str, confidence_score: float, approval_request: str) -> A2HRequest:
    """
    A tool for an agent to request human approval for an action.
    """
    return create_a2h_request(intent, justification, confidence_score, approval_request)

def process_human_response(response: A2HResponse):
    """
    A tool for an agent to process a human's response.
    """
    return response.responseType, response.payload
