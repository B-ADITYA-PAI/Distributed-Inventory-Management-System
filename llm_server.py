import grpc
from concurrent import futures
import time
import inventory_pb2
import inventory_pb2_grpc
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

class LLMServiceServicer(inventory_pb2_grpc.LLMServiceServicer):
    def __init__(self):
        print("Loading CPU-optimized LLM (google/flan-t5-small)...")
        model_name = "google/flan-t5-small"
        # Load tokenizer and model directly onto CPU
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        print("LLM loaded successfully. Server is ready.")

    def getLLMAnswer(self, request, context):
        print(f"Received Request ID: {request.request_id}")
        print(f"Query Task: {request.query}")
        
        # Architecture B prompt context
        prompt = (
            f"You are an AI assistant for a Distributed Inventory Management System. "
            f"Task: {request.query}. "
            f"System Context/Data: {request.context}. "
            f"Provide a concise, professional answer based on the data:"
        )

        # Tokenize and generate response directly
        inputs = self.tokenizer(prompt, return_tensors="pt")
        outputs = self.model.generate(**inputs, max_new_tokens=100)
        generated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

        print(f"Generated Answer: {generated_text}\n")

        # Return structured protobuf response[cite: 1]
        return inventory_pb2.LLMAnswerResponse(
            request_id=request.request_id,
            answer=generated_text
        )

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_LLMServiceServicer_to_server(LLMServiceServicer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    print("Node 1 (LLM Server) started on port 50051.")
    
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()