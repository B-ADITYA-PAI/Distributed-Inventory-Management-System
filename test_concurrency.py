from concurrent.futures import ThreadPoolExecutor

import grpc

import inventory_pb2
import inventory_pb2_grpc

APP_SERVER_ADDR = "localhost:50052"
INITIAL_STOCK = 10
CONCURRENT_ORDERS = 12


def get_mouse_stock(stub, token: str) -> int:
    response = stub.get(inventory_pb2.GetRequest(token=token, type="inventory"))
    for item in response.items:
        if item.id == "item_102":
            return int(item.data.split("Stock: ", 1)[1])
    raise RuntimeError("item_102 not found")


def place_order(stub, token: str) -> str:
    return stub.post(
        inventory_pb2.PostRequest(token=token, type="order", data="item_102:1")
    ).status


def run() -> None:
    channel = grpc.insecure_channel(APP_SERVER_ADDR)
    stub = inventory_pb2_grpc.ClientServiceStub(channel)
    login = stub.login(inventory_pb2.LoginRequest(username="concurrency_test", password="password"))
    if not login.token:
        raise RuntimeError("Concurrency test login failed")

    starting_stock = get_mouse_stock(stub, login.token)
    if starting_stock != INITIAL_STOCK:
        raise RuntimeError(
            f"This test requires fresh Wireless Mouse stock={INITIAL_STOCK}, "
            f"but found {starting_stock}. Restart app_server.py first."
        )

    with ThreadPoolExecutor(max_workers=CONCURRENT_ORDERS) as executor:
        futures = [executor.submit(place_order, stub, login.token) for _ in range(CONCURRENT_ORDERS)]
        results = [future.result() for future in futures]

    successes = sum(result.startswith("SUCCESS_ORDER_PLACED") for result in results)
    failures = sum(result.startswith("FAILED_INSUFFICIENT_STOCK") for result in results)
    final_stock = get_mouse_stock(stub, login.token)

    print("========================================")
    print("Concurrency Test")
    print(f"Starting stock: {starting_stock}")
    print(f"Simultaneous one-unit orders: {CONCURRENT_ORDERS}")
    print(f"Successful orders: {successes}")
    print(f"Insufficient-stock rejections: {failures}")
    print(f"Final stock: {final_stock}")
    print("Expected: 10 successful + 2 rejected + final stock 0")
    print("========================================")

    assert successes == 10, f"Expected 10 successes, got {successes}"
    assert failures == 2, f"Expected 2 stock failures, got {failures}"
    assert final_stock == 0, f"Expected final stock 0, got {final_stock}"

    print("PASS: concurrent orders never oversold the inventory.")


if __name__ == "__main__":
    run()
