from concurrent import futures
import json
import time
from urllib import error, request

import grpc
import inventory_pb2
import inventory_pb2_grpc

OLLAMA_URL = "http://localhost:11434/api/chat"
MODEL_NAME = "qwen3:1.7b"
LLM_SERVER_PORT = 50051


DEMAND_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "predictions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item_id": {"type": "string"},
                    "product_name": {"type": "string"},
                    "predicted_7_day_demand": {
                        "type": "integer",
                        "minimum": 0,
                    },
                    "reason": {"type": "string"},
                },
                "required": [
                    "item_id",
                    "product_name",
                    "predicted_7_day_demand",
                    "reason",
                ],
            },
        }
    },
    "required": ["predictions"],
}


REORDER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "item_id": {"type": "string"},
                    "product_name": {"type": "string"},
                    "reorder": {"type": "boolean"},
                    "reason": {"type": "string"},
                },
                "required": [
                    "item_id",
                    "product_name",
                    "reorder",
                    "reason",
                ],
            },
        }
    },
    "required": ["recommendations"],
}


ANALYTICS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "observations": {
            "type": "array",
            "items": {"type": "string"},
        },
        "actions": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["observations", "actions"],
}


class LLMServiceServicer(inventory_pb2_grpc.LLMServiceServicer):
    """Node 1: gRPC LLM service backed by local Qwen3 through Ollama."""

    def _task_and_schema(self, query: str):
        if query == "llm_demand_prediction":
            task = """
You are the demand forecasting component of a distributed inventory system.

The input contains exactly four products. For each product, you receive the
COMPLETE 30-day historical sales sequence from oldest to newest, plus useful
summary statistics.

Forecast the TOTAL number of units expected to be sold during the NEXT 7 DAYS.
This is a forecast task, not a restatement task.

Forecasting guidance:
- Use the full 30-day history, not only the last 7 values.
- Compare earlier behavior with recent behavior.
- For INCREASING demand, normally forecast somewhat above the latest 7-day total.
- For DECREASING demand, normally forecast somewhat below the latest 7-day total.
- For STABLE demand, a forecast close to the latest 7-day total is reasonable.
- For HIGH variability, avoid extreme forecasts unless the historical pattern supports them.
- Consider the direction and magnitude of the recent change before choosing the integer.

Strict output rules:
- Return exactly one prediction for every supplied product.
- predicted_7_day_demand MUST be a single non-negative WHOLE INTEGER.
- Never return decimals, ranges, fractions, percentages, daily arrays, or seven separate values.
- Do not simply copy the most recent 7-day total without considering the 30-day pattern.
- Keep the reason short and qualitative. Do not put new numerical calculations in the reason.
- Never invent products or data.

Return JSON only using the supplied schema.
""".strip()
            return task, DEMAND_SCHEMA

        if query == "llm_reorder_suggestion":
            task = """
You are the automated replenishment decision component of a distributed inventory system.

The input contains exactly four products. For each product, use CURRENT STOCK
and the previously generated LLM PREDICTED NEXT-7-DAY DEMAND.

Decision rule:
- If current stock is LESS THAN predicted 7-day demand, set reorder=true.
- Otherwise set reorder=false.

The application server will calculate the exact integer reorder quantity from
these validated values. You therefore only need to decide whether a reorder is
required and explain the decision.

Strict output rules:
- Return exactly one decision for every supplied product.
- reorder MUST be a boolean.
- Keep the reason consistent with the boolean decision.
- Never invent products or data.

Return JSON only using the supplied schema.
""".strip()
            return task, REORDER_SCHEMA

        if query == "llm_analytics":
            task = """
You are the inventory analytics component of a distributed inventory system.

The input contains facts already validated by the application server.
Summarize the inventory situation for management.

Discuss:
- overall inventory health
- important demand trends
- products requiring replenishment
- useful management actions

Strict output rules:
- Treat the supplied facts as ground truth.
- Never contradict a supplied stock status, demand trend, or replenishment status.
- Never invent a product.
- Do not perform arithmetic.
- Do not introduce new numeric values in observations or actions.
- Keep the observations and actions concise and professional.

Return JSON only using the supplied schema.
""".strip()
            return task, ANALYTICS_SCHEMA

        raise ValueError(f"Unknown LLM task: {query}")

    def _build_prompt(self, query: str, context: str, schema: dict) -> str:
        task, _ = self._task_and_schema(query)
        return f"""
{task}

DATA:
{context}

JSON SCHEMA:
{json.dumps(schema, indent=2)}

Return JSON only. No markdown. No code fences. No text outside JSON.
""".strip()

    def _call_ollama(self, prompt: str, schema: dict) -> str:
        payload = {
            "model": MODEL_NAME,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a precise inventory AI service. Follow the schema exactly.",
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "think": False,
            "format": schema,
            "options": {
                "temperature": 0,
                "seed": 42,
            },
        }

        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            OLLAMA_URL,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=180) as response:
                data = json.loads(response.read().decode("utf-8"))
        except error.URLError as exc:
            raise RuntimeError(
                "Cannot reach Ollama at http://localhost:11434. "
                "Start Ollama and run: ollama pull qwen3:1.7b"
            ) from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned invalid JSON.") from exc

        answer = data.get("message", {}).get("content", "").strip()
        if not answer:
            raise RuntimeError(f"Ollama returned an empty response: {data}")

        try:
            json.loads(answer)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Ollama returned non-JSON content: {answer}") from exc

        return answer

    def getLLMAnswer(self, request_message, context):
        print(f"[LLM] Request ID: {request_message.request_id}")
        print(f"[LLM] Task: {request_message.query}")

        _, schema = self._task_and_schema(request_message.query)
        prompt = self._build_prompt(
            request_message.query,
            request_message.context,
            schema,
        )
        answer = self._call_ollama(prompt, schema)

        print(f"[LLM] Structured response generated for {request_message.query}\n")
        return inventory_pb2.LLMAnswerResponse(
            request_id=request_message.request_id,
            answer=answer,
        )


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_LLMServiceServicer_to_server(
        LLMServiceServicer(), server
    )
    server.add_insecure_port(f"[::]:{LLM_SERVER_PORT}")
    server.start()

    print("========================================")
    print("Node 1 - LLM Server")
    print(f"gRPC port: {LLM_SERVER_PORT}")
    print(f"Local model: {MODEL_NAME}")
    print("Runtime: Ollama")
    print("Structured JSON output: ENABLED")
    print("Qwen thinking mode: DISABLED")
    print("========================================")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()
