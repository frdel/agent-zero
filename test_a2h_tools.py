import unittest
from a2h import A2HRequest, A2HResponse, ResponseType
from a2h_tools import request_human_approval, process_human_response

class TestA2HTools(unittest.TestCase):

    def test_request_human_approval(self):
        request = request_human_approval(
            intent="Test intent",
            justification="Test justification",
            confidence_score=0.9,
            approval_request="Test approval request",
        )
        self.assertIsInstance(request, A2HRequest)
        self.assertEqual(request.intent, "Test intent")
        self.assertEqual(request.justification, "Test justification")
        self.assertEqual(request.confidenceScore, 0.9)
        self.assertEqual(request.approvalRequest, "Test approval request")
        self.assertIsNotNone(request.traceId)

    def test_process_human_response(self):
        response = A2HResponse(
            traceId="test_trace_id",
            responseType=ResponseType.APPROVE,
        )
        response_type, payload = process_human_response(response)
        self.assertEqual(response_type, ResponseType.APPROVE)
        self.assertIsNone(payload)

    def test_process_human_response_with_payload(self):
        response = A2HResponse(
            traceId="test_trace_id",
            responseType=ResponseType.MODIFY,
            payload={"modifications": "Test modifications"},
        )
        response_type, payload = process_human_response(response)
        self.assertEqual(response_type, ResponseType.MODIFY)
        self.assertEqual(payload, {"modifications": "Test modifications"})

if __name__ == "__main__":
    unittest.main()
