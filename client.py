import grpc

import inventory_pb2
import inventory_pb2_grpc

APP_SERVER_ADDR = "localhost:50052"


def print_ai_response(title: str, response) -> None:
    print(f"\n--- {title} ---")
    if response.items:
        print(response.items[0].data)
    else:
        print(f"ERROR: {response.status}")


def run() -> None:
    channel = grpc.insecure_channel(APP_SERVER_ADDR)
    stub = inventory_pb2_grpc.ClientServiceStub(channel)

    print("========================================")
    print("Distributed Inventory Management Demo")
    print("Milestone 1: gRPC + Local LLM")
    print("========================================")

    # ------------------------------------------------------------------
    # 1. Authentication
    # ------------------------------------------------------------------
    print("\n--- 1. Authentication ---")
    login = stub.login(
        inventory_pb2.LoginRequest(
            username="alice",
            password="password",
        )
    )
    print(f"Status: {login.status}")

    if not login.token:
        print("Login failed. Demo stopped.")
        return

    token = login.token

    # ------------------------------------------------------------------
    # 2. Dataset summary + inventory
    # ------------------------------------------------------------------
    print("\n--- 2. Inventory + Historical Dataset ---")
    print("Products: 12")
    print("Historical observations: 12 products x 30 days = 360 daily sales values")

    dataset_response = stub.get(
        inventory_pb2.GetRequest(token=token, type="inventory_summary")
    )
    if dataset_response.items:
        print(dataset_response.items[0].data)
    else:
        print(f"Dataset summary unavailable: {dataset_response.status}")

    print("\n--- 3. Current Inventory via gRPC ---")
    inventory_response = stub.get(
        inventory_pb2.GetRequest(token=token, type="inventory")
    )
    for item in inventory_response.items:
        print(f"[{item.id}] {item.data}")

    # ------------------------------------------------------------------
    # 3. Order processing
    # ------------------------------------------------------------------
    print("\n--- 4. Order Processing ---")
    order_one = stub.post(
        inventory_pb2.PostRequest(
            token=token,
            type="order",
            data="item_102:4",
        )
    )
    print(f"Buy 4 mice -> {order_one.status}")

    order_two = stub.post(
        inventory_pb2.PostRequest(
            token=token,
            type="order",
            data="item_102:8",
        )
    )
    print(f"Then buy 8 mice -> {order_two.status}")

    invalid_order = stub.post(
        inventory_pb2.PostRequest(
            token=token,
            type="order",
            data="item_102:-1",
        )
    )
    print(f"Negative order -> {invalid_order.status}")

    # ------------------------------------------------------------------
    # 4. LLM demand prediction
    # ------------------------------------------------------------------
    demand = stub.get(
        inventory_pb2.GetRequest(
            token=token,
            type="llm_demand_prediction",
        )
    )
    print_ai_response("5. LLM Demand Prediction", demand)

    # ------------------------------------------------------------------
    # 5. LLM automated reorder suggestion
    # ------------------------------------------------------------------
    reorder = stub.get(
        inventory_pb2.GetRequest(
            token=token,
            type="llm_reorder_suggestion",
        )
    )
    print_ai_response("6. LLM Automated Reorder Suggestion", reorder)

    # ------------------------------------------------------------------
    # 6. LLM inventory analytics
    # ------------------------------------------------------------------
    analytics = stub.get(
        inventory_pb2.GetRequest(
            token=token,
            type="llm_analytics",
        )
    )
    print_ai_response("7. LLM Inventory Analytics", analytics)

    # ------------------------------------------------------------------
    # 7. Logout
    # ------------------------------------------------------------------
    print("\n--- 8. Logout ---")
    logout = stub.logout(
        inventory_pb2.TokenMessage(token=token)
    )
    print(f"Status: {logout.status}")


if __name__ == "__main__":
    run()
