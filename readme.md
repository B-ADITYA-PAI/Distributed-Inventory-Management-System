# Distributed Inventory Management System - Milestone 1

## Project Overview

This project implements Milestone 1 of a Distributed Inventory Management System using:

- Python
- gRPC
- Protocol Buffers
- Ollama for local LLM serving
- Qwen3 1.7B
- Mock historical sales data

The system is split into independent processes:

```text
                         CLIENT
                       client.py
                           |
                           | gRPC :50052
                           v
                 APPLICATION SERVER
                    app_server.py
                           |
                           | gRPC :50051
                           v
                      LLM SERVER
                    llm_server.py
                           |
                           | HTTP localhost:11434
                           v
                         OLLAMA
                           |
                           v
                     Qwen3 1.7B
```

The Application Server owns authentication, inventory state, order processing, concurrency control, mock historical sales data, and orchestration/validation of the AI requests.

The LLM Server is a separate service. It receives AI tasks over gRPC and calls the locally installed Qwen3 1.7B model through Ollama.

---

# 1. Milestone 1 Requirements

| Requirement | How this project implements it |
|---|---|
| Correct stock decrement | Valid orders decrement the selected item's stock. |
| Prevent negative stock levels | Stock validation and decrement occur inside one `threading.Lock` critical section. |
| LLM demand prediction based on historical mock data | Qwen3 receives 30 days of daily sales history and predicts total demand for the next 7 days. |
| Automated reorder suggestions | Qwen3 receives current stock and the previously generated LLM demand forecast. The Application Server validates the returned decision and quantity. |
| Summarized inventory analytics and reports | Qwen3 generates qualitative observations and actions, while exact numerical values are taken from application data. |
| Distributed communication | Client ↔ Application Server and Application Server ↔ LLM Server use gRPC. |
| Local AI | Qwen3 1.7B runs locally through Ollama. |

---

# 2. Mock Dataset

The previous two-product/seven-day example has been expanded into a more realistic Milestone 1 mock dataset:

```text
12 products
×
30 days of historical sales
=
360 daily sales observations
```

The data contains different patterns so the LLM has meaningful history to analyze:

- **Stable:** Laptop, Keyboard, Laptop Stand, HDMI Cable
- **Increasing:** Wireless Mouse, USB-C Charger, Power Bank
- **Decreasing:** Monitor
- **Volatile:** Headphones, Mechanical Keyboard
- **Spiky:** Webcam
- **Low/stable:** SSD

The data is deterministic and stored in `mock_data.py`, so every demo run starts with the same dataset.

---

# 3. Project Files

```text
project/
|
├── app_server.py
├── llm_server.py
├── client.py
├── mock_data.py
├── test_concurrency.py
├── test_ollama.py
├── inventory.proto
├── inventory_pb2.py
├── inventory_pb2_grpc.py
├── generate_proto.sh
├── requirements.txt
└── README_MILESTONE1.md
```

### Responsibilities

**`mock_data.py`**  
Stores the 12 products, initial stock levels, and 30-day mock sales histories.

**`inventory.proto`**  
Defines the gRPC services and messages.

**`inventory_pb2.py`**  
Generated Protocol Buffer message classes.

**`inventory_pb2_grpc.py`**  
Generated gRPC client stubs and server registration code.

**`app_server.py`**  
Node 2. Handles authentication, inventory, orders, concurrency, historical data, LLM orchestration, validation, and report formatting.

**`llm_server.py`**  
Node 1. Receives AI requests by gRPC and calls local Qwen3 through Ollama using structured JSON output.

**`client.py`**  
Runs the end-to-end Milestone 1 demonstration.

**`test_concurrency.py`**  
Sends 12 simultaneous one-unit mouse orders against an initial stock of 10.

**`test_ollama.py`**  
Checks that Ollama is reachable and the model can answer locally.

---

# 4. Prerequisites

Install:

1. Python 3
2. Ollama
3. Qwen3 1.7B

The project uses local inference. No cloud AI API key is required.

---

# 5. macOS Setup

## 5.1 Install and verify Ollama

Install Ollama for macOS and start it.

```bash
ollama --version
```

## 5.2 Download the model

```bash
ollama pull qwen3:1.7b
```

Verify:

```bash
ollama list
```

Optional direct test:

```bash
ollama run qwen3:1.7b
```

Exit with `Ctrl+C`.

## 5.3 Create a virtual environment

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

## 5.4 Regenerate protobuf/gRPC files

```bash
chmod +x generate_proto.sh
./generate_proto.sh
```

Or directly:

```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. inventory.proto
```

This creates:

```text
inventory_pb2.py
inventory_pb2_grpc.py
```

## 5.5 Verify gRPC imports

```bash
python -c "import inventory_pb2; import inventory_pb2_grpc; print('PROTOBUF + gRPC OK')"
```

## 5.6 Test Ollama

```bash
python test_ollama.py
```

---

# 6. Windows Setup

## 6.1 Install and verify Ollama

Install Ollama for Windows, then open a new PowerShell window.

```powershell
ollama --version
```

## 6.2 Download the model

```powershell
ollama pull qwen3:1.7b
```

Verify:

```powershell
ollama list
```

Optional direct test:

```powershell
ollama run qwen3:1.7b
```

Exit with `Ctrl+C`.

## 6.3 Create a virtual environment

```powershell
py -m venv .venv
```

Activate:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation for the current process:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate again:

```powershell
.\.venv\Scripts\Activate.ps1
```

Upgrade pip:

```powershell
python -m pip install --upgrade pip
```

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

## 6.4 Generate protobuf/gRPC files

```powershell
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. inventory.proto
```

## 6.5 Verify gRPC imports

```powershell
python -c "import inventory_pb2; import inventory_pb2_grpc; print('PROTOBUF + gRPC OK')"
```

## 6.6 Test Ollama

```powershell
python test_ollama.py
```

---

# 7. Start the Distributed System

Use three terminal windows.

## Terminal 1: LLM Server

### macOS/Linux

```bash
source .venv/bin/activate
python llm_server.py
```

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
python llm_server.py
```

Expected startup information:

```text
Node 1 - LLM Server
gRPC port: 50051
Ollama model: qwen3:1.7b
Structured outputs: ENABLED
Thinking mode: DISABLED
```

## Terminal 2: Application Server

### macOS/Linux

```bash
source .venv/bin/activate
python app_server.py
```

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
python app_server.py
```

Expected startup information:

```text
Node 2 - Application Server
gRPC port: 50052
Inventory: 12 products
History: 30 days per product
Historical observations: 360
```

## Terminal 3: Client

### macOS/Linux

```bash
source .venv/bin/activate
python client.py
```

### Windows PowerShell

```powershell
.\.venv\Scripts\Activate.ps1
python client.py
```

---

# 8. How the LLM Features Work

## 8.1 Demand prediction

The Application Server sends the full 30-day sales history to the LLM Server.

To keep prompts manageable for Qwen3 1.7B, products are sent in batches of four.

The LLM must return one integer forecast for each product:

```json
{
  "predictions": [
    {
      "item_id": "item_102",
      "product_name": "Wireless Mouse",
      "predicted_7_day_demand": 32,
      "reason": "Recent demand is relatively strong and increasing."
    }
  ]
}
```

Structured JSON output prevents the previous problem of receiving values such as:

```text
[4.57, 4.57, 4.57, ...]
```

The application server accepts only non-negative whole-number forecasts.

A sanity guardrail rejects clearly pathological values. This is a safety mechanism, not the forecasting algorithm itself. The actual forecast is still generated by the LLM.

## 8.2 Reorder recommendation

The same LLM forecast is passed to the reorder task together with current stock.

The LLM returns:

```json
{
  "recommendations": [
    {
      "item_id": "item_102",
      "product_name": "Wireless Mouse",
      "reorder": true,
      "recommended_quantity": 26,
      "reason": "Current stock is below predicted demand."
    }
  ]
}
```

The Application Server validates the final decision:

```text
current stock < predicted 7-day demand
        -> REORDER
        -> quantity = predicted demand - current stock

otherwise
        -> DO NOT REORDER
        -> quantity = 0
```

The displayed recommendation therefore cannot contradict the inventory state even if the small LLM makes an arithmetic mistake.

## 8.3 Inventory analytics

The Application Server calculates exact numeric values from the source data.

The LLM receives validated qualitative facts such as:

```text
Product: Wireless Mouse
Stock status: LOW
Demand trend: INCREASING
Replenishment status: REORDER
```

The LLM generates the observations and management actions. Exact numbers shown in the report are rendered by the Application Server.

---

# 9. Normal Demo Behaviour

The client demonstrates:

```text
Authentication
      ↓
12-product inventory overview
      ↓
Successful order
      ↓
Insufficient-stock rejection
      ↓
Negative-quantity rejection
      ↓
LLM demand forecasts
      ↓
LLM reorder recommendations
      ↓
LLM analytics report
      ↓
Logout
```

The first order buys four Wireless Mice:

```text
10 -> 6
```

A second request for eight mice is rejected because only six remain.

A negative order is rejected as `INVALID_QUANTITY`.

---

# 10. Concurrency Test

The concurrency test must be run against a freshly started Application Server because inventory is held in memory.

Initial Wireless Mouse stock:

```text
10 units
```

The test launches:

```text
12 simultaneous one-unit orders
```

Expected result:

```text
Successful orders: 10
Insufficient-stock rejections: 2
Final stock: 0
```

Run:

```bash
python test_concurrency.py
```

or on Windows:

```powershell
python test_concurrency.py
```

If it reports starting stock other than 10, restart `app_server.py` and run it again.

---

# 11. Limitations

This is a Milestone 1 prototype and should be interpreted within that scope.

## Synthetic historical data

The historical sales dataset is mock data created for demonstration. It is not derived from a real company's sales database.

## LLM-based forecasting is an estimate

Qwen3 1.7B is a general-purpose instruction-following language model. It is prompted to perform demand forecasting from historical sales. It is not a dedicated forecasting model trained on real inventory time series.

## LLM numerical reliability

A language model can make arithmetic or reasoning mistakes. Structured outputs, deterministic settings, sanity checks, and Application Server validation are used to reduce this risk. The application server remains the source of truth for inventory arithmetic and final reorder quantities.

## In-memory storage

Inventory and authentication sessions are stored in Python memory. No persistent database is used. Restarting the Application Server resets inventory and sessions.

## Demo authentication

The authentication mechanism uses a fixed demonstration password and accepts any non-empty username. It is intended only to demonstrate the request/session flow.

## Local single-machine deployment

The architecture is distributed into separate services/processes, but the demonstration normally runs them on one computer using `localhost`. A production version could deploy services on different machines or containers.

## gRPC security

The demonstration uses insecure local gRPC channels. Production TLS, certificate management, encrypted transport, and stronger authentication are outside Milestone 1.

## Limited scalability

There is one in-memory inventory instance. The project does not yet implement database replication, load balancing, service discovery, distributed caching, or horizontal scaling.

## LLM batching

Twelve products are forecast in three four-product LLM requests. Batching reduces the prompt size for the small local model, but the LLM does not process every product in a single forecasting prompt.

## Reorder is advisory

The system generates a reorder recommendation but does not automatically purchase inventory from an external supplier.

## Model availability

The AI features depend on Ollama and the local `qwen3:1.7b` model being available. The core inventory service and order logic are separate from the model runtime.

---

# 12. Troubleshooting

## `Cannot reach Ollama`

Make sure Ollama is running and execute:

```bash
ollama list
```

Confirm that `qwen3:1.7b` is installed.

## gRPC/protobuf import error

Regenerate the generated files from the local `inventory.proto`:

```bash
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. inventory.proto
```

Also make sure the virtual environment is activated and dependencies were installed from `requirements.txt`.

## Port already in use

Make sure an older `app_server.py` is not already running on port `50052` and an older `llm_server.py` is not already running on port `50051`.

---

# 13. Final Milestone 1 Architecture

```text
                    30-DAY MOCK SALES DATA
                              |
                              v
                     APPLICATION SERVER
                              |
                              | gRPC
                              v
                         LLM SERVER
                              |
                              | local HTTP
                              v
                            OLLAMA
                              |
                              v
                        QWEN3 1.7B
                              |
              +---------------+---------------+
              |               |               |
              v               v               v
        Demand Forecast   Reorder Advice   Analytics
              |               |               |
              +---------------+---------------+
                              |
                              v
                     APPLICATION SERVER
                              |
                              v
                           CLIENT
```

The project demonstrates the complete Milestone 1 pipeline: concurrency-safe order processing, mock historical inventory data, LLM-based demand prediction, automated reorder suggestions, and summarized inventory analytics delivered through a distributed gRPC architecture.
