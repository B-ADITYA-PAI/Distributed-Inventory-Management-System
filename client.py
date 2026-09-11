import grpc
import inventory_pb2
import inventory_pb2_grpc

APP_SERVER_ADDR = 'localhost:50052'

def run():
    channel = grpc.insecure_channel(APP_SERVER_ADDR)
    stub = inventory_pb2_grpc.ClientServiceStub(channel)

    print("--- 1. Authenticating Client ---")
    login_res = stub.login(inventory_pb2.LoginRequest(username="alice", password="password"))
    print(f"Login Response -> Status: {login_res.status}, Token: {login_res.token}\n")
    token = login_res.token

    print("--- 2. Fetching Current Inventory ---")
    get_res = stub.get(inventory_pb2.GetRequest(token=token, type="inventory"))
    for item in get_res.items:
        print(f"[{item.id}] {item.data}")
    print()

    print("--- 3. Testing Order Decrement & Concurrency Guard ---")
    # Initial Wireless Mouse stock is 10. Order 4 units.
    order1 = stub.post(inventory_pb2.PostRequest(token=token, type="order", data="item_102:4"))
    print(f"Order 1 (Buy 4 mice) -> {order1.status}")

    # Attempt to order 8 units when only 6 remain. Should fail gracefully.
    order2 = stub.post(inventory_pb2.PostRequest(token=token, type="order", data="item_102:8"))
    print(f"Order 2 (Buy 8 mice) -> {order2.status}\n")

    print("--- 4. Querying LLM Server Features via App Server ---")
    # Task 1: Demand Prediction
    pred_res = stub.get(inventory_pb2.GetRequest(token=token, type="llm_demand_prediction"))
    print(f"[LLM Demand Prediction]: {pred_res.items[0].data if pred_res.items else pred_res.status}")

    # Task 2: Reorder Suggestion
    reorder_res = stub.get(inventory_pb2.GetRequest(token=token, type="llm_reorder_suggestion"))
    print(f"[LLM Reorder Suggestion]: {reorder_res.items[0].data if reorder_res.items else reorder_res.status}")

    # Task 3: Inventory Analytics Report
    analytics_res = stub.get(inventory_pb2.GetRequest(token=token, type="llm_analytics"))
    print(f"[LLM Analytics Summary]: {analytics_res.items[0].data if analytics_res.items else analytics_res.status}\n")

    print("--- 5. Logging Out ---")
    logout_res = stub.logout(inventory_pb2.TokenMessage(token=token))
    print(f"Logout Response -> {logout_res.status}")

if __name__ == '__main__':
    run()