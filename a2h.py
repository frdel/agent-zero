from dataclasses import dataclass
from enum import Enum
import uuid

class ResponseType(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    MODIFY = "modify"
    DEFER = "defer"

@dataclass
class A2HRequest:
    intent: str
    justification: str
    confidenceScore: float
    approvalRequest: str
    traceId: str = str(uuid.uuid4())

@dataclass
class A2HResponse:
    traceId: str
    responseType: ResponseType
    payload: dict | None = None


def create_a2h_request(intent: str, justification: str, confidence_score: float, approval_request: str) -> A2HRequest:
    """Creates an A2H request."""
    return A2HRequest(
        intent=intent,
        justification=justification,
        confidenceScore=confidence_score,
        approvalRequest=approval_request,
    )


def create_a2h_response(trace_id: str, response_type: ResponseType, payload: dict | None = None) -> A2HResponse:
    """Creates an A2H response."""
    return A2HResponse(
        traceId=trace_id,
        responseType=response_type,
        payload=payload,
    )
