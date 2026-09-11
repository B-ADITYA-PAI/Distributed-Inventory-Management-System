# Distributed Inventory Management System (Architecture B)

This repository contains the Milestone 1 implementation of the Distributed Inventory Management System. The system uses gRPC for inter-service messaging and integrates a localized, CPU-optimized Large Language Model (LLM) for context-aware inventory assistance. All code is implemented exclusively in Python.

## Project Structure

* **`inventory.proto`**: The gRPC Protocol Buffer definitions for Client, Application, and LLM services.


* **`llm_server.py` (Node 1)**: An independent server hosting a lightweight, domain-specific LLM (`google/flan-t5-small`) for demand prediction, reorder suggestions, and analytics.


* **`app_server.py` (Node 2)**: The core application server managing business logic, authentication, and inventory state with concurrency control to explicitly prevent negative stock levels.


* **`client.py` (Node 5)**: A client simulator to test concurrent user interactions, stock decrementing, and LLM queries.



## Prerequisites & Setup

The project requires Python 3. It is highly recommended to use a virtual environment to avoid system policy conflicts when installing PyTorch.

1. **Create and Activate a Virtual Environment:**
Open your terminal in the project directory and run:
```powershell
python -m venv .venv

```


2. **Install Dependencies:**
Install the required libraries for gRPC communication and the local LLM:
```powershell
.\.venv\Scripts\python.exe -m pip install grpcio grpcio-tools torch transformers

```


3. **Compile the Protocol Buffers:**
Generate the required Python gRPC code from the `.proto` file:
```powershell
.\.venv\Scripts\python.exe -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. inventory.proto

```


This will generate `inventory_pb2.py` and `inventory_pb2_grpc.py`.

## Deployment and Usage Instructions

To simulate the distributed environment, you must run the nodes simultaneously in separate terminal windows.

**Terminal 1: Start the LLM Server (Node 1)**
This server operates independently and listens on port 50051. Note: The first execution will download the model files from Hugging Face (~300MB).

```powershell
.\.venv\Scripts\python.exe llm_server.py

```

**Terminal 2: Start the Application Server (Node 2)**
Open a second terminal window. This server manages core logic and connects to Node 1 via gRPC. It listens on port 50052.

```powershell
.\.venv\Scripts\python.exe app_server.py

```

**Terminal 3: Run the Client Simulator (Node 5)**
Open a third terminal window. This script simulates client interactions and demonstrates the required functionality.

```powershell
.\.venv\Scripts\python.exe client.py

```

### Expected Client Output

Running the client simulator will demonstrate:

1. Successful user authentication and token generation.


2. Safe processing of inventory orders.


3. Concurrency control successfully blocking orders that would result in negative stock.


4. Context-aware AI responses for demand predictions, reorder suggestions, and inventory analytics.