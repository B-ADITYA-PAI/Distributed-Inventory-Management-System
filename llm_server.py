import grpc
from concurrent import futures
import time
import inventory_pb2
import inventory_pb2_grpc
from transformers import pipeline

class LLMServiceServicer(inventory_pb2_grpc.LLMServiceServicer):
    def __init__(self):
        print("Loading CPU-optimized LLM (google/flan-t5-small)...")
        # device=-1 forces CPU execution. This model is lightweight and context-aware.
        self.llm = pipeline("text2text-generation", model="google/flan-t5-small", device=-1)
        print("LLM loaded successfully. Server is ready.")

    def getLLMAnswer(self, request, context):
        print(f"Received Request ID: {request.request_id}")
        print(f"Query Task: {request.query}")
        
        # Architecture B specifically requires handling 3 types of tasks. 
        # The App Server will pass the task type in 'query' and mock data in 'context'.
        prompt = (
            f"You are an AI assistant for a Distributed Inventory Management System. "
            f"Task: {request.query}. "
            f"System Context/Data: {request.context}. "
            f"Provide a concise, professional answer based on the data:"
        )

        # Generate the response using the local model
        output = self.llm(prompt, max_length=150, truncation=True)
        generated_text = output[0]['generated_text']

        print(f"Generated Answer: {generated_text}\n")

        # Return the structured response defined in your .proto file
        return inventory_pb2.LLMAnswerResponse(
            request_id=request.request_id,
            answer=generated_text
        )

def serve():
    # Create a gRPC server with a thread pool to handle concurrent requests
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    
    # Register the LLM Servicer with the gRPC server
    inventory_pb2_grpc.add_LLMServiceServicer_to_server(LLMServiceServicer(), server)
    
    # Listen on port 50051 (Node 1)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Node 1 (LLM Server) started on port 50051.")
    
    try:
        # Keep the server running
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()