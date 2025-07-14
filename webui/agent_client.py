import grpc
from agent_core.proto import agent_pb2, agent_pb2_grpc

class AgentClient:
    def __init__(self, host='localhost', port=50051):
        self.channel = grpc.insecure_channel(f"{host}:{port}")
        self.stub = agent_pb2_grpc.AgentCoreStub(self.channel)

    def inference(self, input_text):
        req = agent_pb2.InferenceRequest(input=input_text)
        resp = self.stub.Inference(req)
        return resp.output, resp.agent_version

    def status(self):
        req = agent_pb2.StatusRequest()
        resp = self.stub.Status(req)
        return resp.agent_version, resp.status, resp.uptime

    def hotswap(self, new_image):
        req = agent_pb2.HotSwapRequest(new_image=new_image)
        resp = self.stub.HotSwap(req)
        return resp.success, resp.message
