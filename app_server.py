import grpc
from concurrent import futures
import time
import threading
import uuid
import inventory_pb2
import inventory_pb2_grpc

# Address of Node 1 (LLM Server)
LLM_SERVER_ADDR = 'localhost:50051'

class ClientServiceServicer(inventory_pb2_grpc.ClientServiceServicer):
    def __init__(self):
        # In-memory storage for authentication sessions
        self.sessions = {}  # token -> username
        
        # Initial inventory state
        self.inventory = {
            "item_101": {"name": "Laptop", "stock": 50},
            "item_102": {"name": "Wireless Mouse", "stock": 10}
        }
        
        # Thread lock for concurrency control (prevents negative stock)
        self.lock = threading.Lock()
        
        # Establish gRPC client connection to Node 1 (LLM Server)
        channel = grpc.insecure_channel(LLM_SERVER_ADDR)
        self.llm_stub = inventory_pb2_grpc.LLMServiceStub(channel)

    def login(self, request, context):
        # Basic authentication check
        if request.username and request.password == "password":
            token = str(uuid.uuid4())
            self.sessions[token] = request.username
            print(f"[Auth] User '{request.username}' logged in successfully.")
            return inventory_pb2.LoginResponse(status="SUCCESS", token=token)
        return inventory_pb2.LoginResponse(status="FAILED_INVALID_CREDENTIALS")

    def logout(self, request, context):
        if request.token in self.sessions:
            user = self.sessions.pop(request.token)
            print(f"[Auth] User '{user}' logged out.")
            return inventory_pb2.StatusResponse(status="LOGGED_OUT")
        return inventory_pb2.StatusResponse(status="INVALID_TOKEN")

    def post(self, request, context):
        # Verify active session token
        if request.token not in self.sessions:
            return inventory_pb2.StatusResponse(status="UNAUTHORIZED")

        # Process order requests safely
        if request.type == "order":
            # Format expected in data field: "item_id:quantity" (e.g., "item_102:4")
            try:
                item_id, qty_str = request.data.split(":")
                qty = int(qty_str)
            except ValueError:
                return inventory_pb2.StatusResponse(status="INVALID_DATA_FORMAT")

            # Concurrency control lock block
            with self.lock:
                if item_id not in self.inventory:
                    return inventory_pb2.StatusResponse(status="ITEM_NOT_FOUND")

                current_stock = self.inventory[item_id]["stock"]
                
                # Explicit negative stock prevention check
                if current_stock < qty:
                    print(f"[Order Blocked] Insufficient stock for {item_id}. Requested: {qty}, Available: {current_stock}")
                    return inventory_pb2.StatusResponse(
                        status=f"FAILED_INSUFFICIENT_STOCK (Available: {current_stock})"
                    )

                # Safely decrement stock
                self.inventory[item_id]["stock"] -= qty
                remaining = self.inventory[item_id]["stock"]
                print(f"[Order Successful] {item_id} decremented by {qty}. Remaining stock: {remaining}")
                return inventory_pb2.StatusResponse(status=f"SUCCESS_ORDER_PLACED (Remaining: {remaining})")

        return inventory_pb2.StatusResponse(status="UNKNOWN_TYPE")

    def get(self, request, context):
        # Verify active session token
        if request.token not in self.sessions:
            return inventory_pb2.GetResponse(status="UNAUTHORIZED", items=[])

        # Query current stock levels
        if request.type == "inventory":
            items = []
            with self.lock:
                for item_id, details in self.inventory.items():
                    data_str = f"Name: {details['name']}, Stock: {details['stock']}"
                    items.append(inventory_pb2.DataItem(id=item_id, data=data_str))
            return inventory_pb2.GetResponse(status="SUCCESS", items=items)

        # Route Architecture B LLM queries to Node 1 (Demand Prediction, Reorder Suggestions, Analytics)
        elif request.type in ["llm_demand_prediction", "llm_reorder_suggestion", "llm_analytics"]:
            with self.lock:
                inv_summary = ", ".join([f"{d['name']}: {d['stock']} units" for d in self.inventory.values()])
            
            req_id = str(uuid.uuid4())
            try:
                # Forward request over gRPC to LLM Server
                llm_resp = self.llm_stub.getLLMAnswer(
                    inventory_pb2.LLMRequest(
                        request_id=req_id,
                        query=request.type,
                        context=f"Current Stock: {inv_summary}"
                    )
                )
                item = inventory_pb2.DataItem(id=req_id, data=llm_resp.answer)
                return inventory_pb2.GetResponse(status="SUCCESS", items=[item])
            except Exception as e:
                return inventory_pb2.GetResponse(status=f"LLM_ERROR: {str(e)}", items=[])

        return inventory_pb2.GetResponse(status="UNKNOWN_TYPE", items=[])


class AppServerServiceServicer(inventory_pb2_grpc.AppServerServiceServicer):
    def processBusinessRequest(self, request, context):
        print(f"[Internal App Logic] Request ID: {request.request_id}, Context: {request.context}")
        return inventory_pb2.StatusResponse(status="BUSINESS_REQUEST_PROCESSED")


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_ClientServiceServicer_to_server(ClientServiceServicer(), server)
    inventory_pb2_grpc.add_AppServerServiceServicer_to_server(AppServerServiceServicer(), server)
    
    # Node 2 listens on port 50052
    server.add_insecure_port('[::]:50052')
    server.start()
    print("Node 2 (Application Server) started on port 50052.")
    
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)

if __name__ == '__main__':
    serve()