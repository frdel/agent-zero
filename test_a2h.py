import unittest
from a2h import A2HRequest, A2HResponse, ResponseType, create_a2h_request, create_a2h_response

class TestA2H(unittest.TestCase):

    def test_create_a2h_request(self):
        request = create_a2h_request(
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

    def test_create_a2h_response(self):
        response = create_a2h_response(
            trace_id="test_trace_id",
            response_type=ResponseType.APPROVE,
        )
        self.assertIsInstance(response, A2HResponse)
        self.assertEqual(response.traceId, "test_trace_id")
        self.assertEqual(response.responseType, ResponseType.APPROVE)
        self.assertIsNone(response.payload)

    def test_create_a2h_response_with_payload(self):
        response = create_a2h_response(
            trace_id="test_trace_id",
            response_type=ResponseType.MODIFY,
            payload={"modifications": "Test modifications"},
        )
        self.assertIsInstance(response, A2HResponse)
        self.assertEqual(response.traceId, "test_trace_id")
        self.assertEqual(response.responseType, ResponseType.MODIFY)
        self.assertEqual(response.payload, {"modifications": "Test modifications"})

if __name__ == "__main__":
    unittest.main()
