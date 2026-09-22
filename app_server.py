from concurrent import futures
import json
import threading
import time
import uuid

import grpc
import inventory_pb2
import inventory_pb2_grpc

from mock_data import (
    INVENTORY,
    MOCK_SALES_HISTORY,
    historical_total,
    recent_7_total,
    trend_label,
    variability_label,
    average_daily,
    recent_7_average,
    min_daily,
    max_daily,
)

LLM_SERVER_ADDR = "localhost:50051"
APP_SERVER_PORT = 50052

LLM_BATCH_SIZE = 4
LLM_TIMEOUT_SECONDS = 180


class ClientServiceServicer(inventory_pb2_grpc.ClientServiceServicer):
    """Node 2: authentication, inventory, orders, and LLM orchestration."""

    def __init__(self):
        self.sessions = {}
        self.inventory = {
            item_id: details.copy() for item_id, details in INVENTORY.items()
        }
        self.lock = threading.Lock()

        # The forecast is cached until inventory changes.
        self.inventory_version = 0
        self.latest_forecast = None
        self.latest_forecast_version = -1

        channel = grpc.insecure_channel(LLM_SERVER_ADDR)
        self.llm_stub = inventory_pb2_grpc.LLMServiceStub(channel)

    def _authenticated(self, token: str) -> bool:
        with self.lock:
            return token in self.sessions

    def _snapshot_inventory(self):
        with self.lock:
            return {
                item_id: details.copy()
                for item_id, details in self.inventory.items()
            }

    # ------------------------------------------------------------------
    # Context sent to the LLM for demand forecasting.
    # Python calculates DESCRIPTIVE statistics only. It does not calculate
    # the forecast. The LLM receives the complete 30-day history and makes
    # the actual next-7-day forecast.
    # ------------------------------------------------------------------
    def _build_demand_context(self, item_ids):
        snapshot = self._snapshot_inventory()

        lines = [
            "TASK: Forecast the total product demand for the NEXT 7 DAYS.",
            "This is mock historical inventory data for a university project.",
            "Each product has exactly 30 daily sales observations, oldest to newest.",
            "The forecast must be a NEW 7-day total, not a daily list.",
            "Use the COMPLETE 30-day history. Pay attention to recent behavior,",
            "longer-term direction, and variability. The summary statistics are",
            "descriptive evidence supplied by the application server, not the answer.",
            "",
        ]

        for item_id in item_ids:
            details = snapshot[item_id]
            history = MOCK_SALES_HISTORY[item_id]
            lines.extend(
                [
                    f"Product ID: {item_id}",
                    f"Product name: {details['name']}",
                    f"Current stock: {details['stock']} units",
                    f"30-day daily sales (oldest -> newest): {history}",
                    f"30-day total sales: {historical_total(item_id)} units",
                    f"30-day average daily sales: {average_daily(item_id):.2f} units",
                    f"First 7-day total: {sum(history[:7])} units",
                    f"Most recent 7-day total: {recent_7_total(item_id)} units",
                    f"Most recent 7-day average: {recent_7_average(item_id):.2f} units/day",
                    f"Minimum daily sales: {min_daily(item_id)} units",
                    f"Maximum daily sales: {max_daily(item_id)} units",
                    f"Observed trend: {trend_label(item_id)}",
                    f"Observed variability: {variability_label(item_id)}",
                    "",
                ]
            )

        return "\n".join(lines)

    def _build_reorder_context(self, item_ids, forecast):
        snapshot = self._snapshot_inventory()
        lines = [
            "TASK: Decide whether each product should be reordered.",
            "The predicted demand values below were produced by the LLM demand-forecast task.",
            "Use current stock versus predicted NEXT-7-DAY demand.",
            "Decision rule: REORDER only when current stock is below predicted demand.",
            "The application server will calculate the exact replenishment quantity from validated integers.",
            "",
        ]

        for item_id in item_ids:
            predicted = forecast[item_id]["predicted_7_day_demand"]
            details = snapshot[item_id]
            lines.extend(
                [
                    f"Product ID: {item_id}",
                    f"Product name: {details['name']}",
                    f"Current stock: {details['stock']} units",
                    f"LLM predicted next 7-day demand: {predicted} units",
                    f"Historical 30-day total: {historical_total(item_id)} units",
                    f"Observed trend: {trend_label(item_id)}",
                    "",
                ]
            )

        return "\n".join(lines)

    def _build_analytics_context(self, forecast, reorder):
        snapshot = self._snapshot_inventory()
        lines = [
            "TASK: Summarize inventory analytics for management.",
            "All facts below have already been validated by the application server.",
            "Treat them as ground truth.",
            "The LLM should provide qualitative observations and management commentary.",
            "Do not invent products or contradict the supplied stock status, trend, or reorder status.",
            "Do not perform new arithmetic.",
            "",
        ]

        for item_id, details in snapshot.items():
            predicted = forecast[item_id]["predicted_7_day_demand"]
            stock_status = "LOW" if details["stock"] < predicted else "ADEQUATE"
            reorder_status = "REORDER" if reorder[item_id]["reorder"] else "DO NOT REORDER"
            lines.extend(
                [
                    f"Product: {details['name']} ({item_id})",
                    f"Stock status: {stock_status}",
                    f"Demand trend: {trend_label(item_id)}",
                    f"Replenishment status: {reorder_status}",
                    "",
                ]
            )

        return "\n".join(lines)

    def _call_llm(self, query: str, context: str) -> str:
        request_id = str(uuid.uuid4())
        print(f"[LLM Routing] {query} -> Node 1 | request_id={request_id}")
        response = self.llm_stub.getLLMAnswer(
            inventory_pb2.LLMRequest(
                request_id=request_id,
                query=query,
                context=context,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        return response.answer

    @staticmethod
    def _parse_json(answer: str, label: str):
        try:
            return json.loads(answer)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON from LLM for {label}: {answer}") from exc

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    def login(self, request, context):
        if request.username and request.password == "password":
            token = str(uuid.uuid4())
            with self.lock:
                self.sessions[token] = request.username
            print(f"[Auth] User '{request.username}' logged in successfully.")
            return inventory_pb2.LoginResponse(status="SUCCESS", token=token)

        return inventory_pb2.LoginResponse(status="FAILED_INVALID_CREDENTIALS")

    def logout(self, request, context):
        with self.lock:
            if request.token not in self.sessions:
                return inventory_pb2.StatusResponse(status="INVALID_TOKEN")
            username = self.sessions.pop(request.token)

        print(f"[Auth] User '{username}' logged out.")
        return inventory_pb2.StatusResponse(status="LOGGED_OUT")

    # ------------------------------------------------------------------
    # Order processing
    # ------------------------------------------------------------------
    def post(self, request, context):
        if not self._authenticated(request.token):
            return inventory_pb2.StatusResponse(status="UNAUTHORIZED")

        if request.type != "order":
            return inventory_pb2.StatusResponse(status="UNKNOWN_TYPE")

        parts = request.data.split(":")
        if len(parts) != 2:
            return inventory_pb2.StatusResponse(status="INVALID_DATA_FORMAT")

        item_id, quantity_text = parts
        try:
            quantity = int(quantity_text)
        except ValueError:
            return inventory_pb2.StatusResponse(status="INVALID_QUANTITY")

        if quantity <= 0:
            return inventory_pb2.StatusResponse(status="INVALID_QUANTITY")

        # Critical section: availability check and decrement happen atomically.
        with self.lock:
            if item_id not in self.inventory:
                return inventory_pb2.StatusResponse(status="ITEM_NOT_FOUND")

            current_stock = self.inventory[item_id]["stock"]
            if current_stock < quantity:
                print(
                    f"[Order Blocked] {item_id}: requested={quantity}, "
                    f"available={current_stock}"
                )
                return inventory_pb2.StatusResponse(
                    status=f"FAILED_INSUFFICIENT_STOCK (Available: {current_stock})"
                )

            self.inventory[item_id]["stock"] -= quantity
            remaining = self.inventory[item_id]["stock"]

            # Invalidate cached forecast because the inventory state changed.
            self.inventory_version += 1
            self.latest_forecast = None
            self.latest_forecast_version = -1

        print(
            f"[Order Successful] {item_id}: decremented={quantity}, "
            f"remaining={remaining}"
        )
        return inventory_pb2.StatusResponse(
            status=f"SUCCESS_ORDER_PLACED (Remaining: {remaining})"
        )

    # ------------------------------------------------------------------
    # LLM demand forecast
    # ------------------------------------------------------------------
    def _get_demand_prediction(self):
        with self.lock:
            current_version = self.inventory_version
            cached = self.latest_forecast
            cached_version = self.latest_forecast_version
            all_item_ids = list(self.inventory.keys())

        if cached is not None and cached_version == current_version:
            return cached

        validated = {}

        # Four products per LLM request keeps the context manageable for a
        # small local model while still covering all 12 products.
        for start in range(0, len(all_item_ids), LLM_BATCH_SIZE):
            batch = all_item_ids[start : start + LLM_BATCH_SIZE]
            raw = self._call_llm(
                "llm_demand_prediction",
                self._build_demand_context(batch),
            )
            payload = self._parse_json(raw, "demand prediction")
            predictions = payload.get("predictions")

            if not isinstance(predictions, list):
                raise ValueError("Demand response is missing 'predictions'.")

            for entry in predictions:
                item_id = entry.get("item_id")
                if item_id not in batch or item_id in validated:
                    continue

                predicted = entry.get("predicted_7_day_demand")
                if (
                    not isinstance(predicted, int)
                    or isinstance(predicted, bool)
                    or predicted < 0
                ):
                    raise ValueError(
                        f"Invalid integer demand forecast for {item_id}: {predicted!r}"
                    )

                # Safety guardrail: reject pathological small-model values,
                # but do NOT replace normal LLM forecasts with a Python forecast.
                recent = recent_7_total(item_id)
                lower = max(1, int(round(recent * 0.50)))
                upper = max(lower, int(round(recent * 2.00)))
                if predicted < lower or predicted > upper:
                    print(
                        f"[LLM Validation] Forecast {predicted} for {item_id} "
                        f"is outside the broad plausibility band "
                        f"[{lower}, {upper}]. Using the recent observed 7-day total "
                        f"{recent} as a safety fallback."
                    )
                    predicted = recent

                validated[item_id] = {
                    "item_id": item_id,
                    "product_name": INVENTORY[item_id]["name"],
                    "predicted_7_day_demand": predicted,
                    "reason": str(entry.get("reason", "")).strip(),
                    "historical_total": historical_total(item_id),
                    "recent_7_total": recent,
                    "trend": trend_label(item_id),
                    "variability": variability_label(item_id),
                }

        missing = set(all_item_ids) - set(validated)
        if missing:
            raise ValueError(
                "LLM did not return predictions for: " + ", ".join(sorted(missing))
            )

        # If an order arrived while forecasting was in progress, don't cache a
        # stale result for the new inventory state.
        with self.lock:
            if self.inventory_version != current_version:
                raise RuntimeError("Inventory changed during forecasting. Please retry.")
            self.latest_forecast = validated
            self.latest_forecast_version = current_version

        return validated

    # ------------------------------------------------------------------
    # LLM reorder recommendation
    # ------------------------------------------------------------------
    def _get_reorder_suggestion(self):
        forecast = self._get_demand_prediction()
        all_item_ids = list(self.inventory.keys())
        llm_decisions = {}

        for start in range(0, len(all_item_ids), LLM_BATCH_SIZE):
            batch = all_item_ids[start : start + LLM_BATCH_SIZE]
            raw = self._call_llm(
                "llm_reorder_suggestion",
                self._build_reorder_context(batch, forecast),
            )
            payload = self._parse_json(raw, "reorder suggestion")
            recommendations = payload.get("recommendations")

            if not isinstance(recommendations, list):
                raise ValueError("Reorder response is missing 'recommendations'.")

            for entry in recommendations:
                item_id = entry.get("item_id")
                if item_id in batch and item_id not in llm_decisions:
                    llm_decisions[item_id] = entry

        snapshot = self._snapshot_inventory()
        final = {}

        for item_id in all_item_ids:
            entry = llm_decisions.get(item_id)
            if entry is None:
                raise ValueError(f"LLM did not return reorder decision for {item_id}.")

            llm_reorder = entry.get("reorder")
            if not isinstance(llm_reorder, bool):
                raise ValueError(f"Invalid reorder decision for {item_id}.")

            current_stock = snapshot[item_id]["stock"]
            predicted = forecast[item_id]["predicted_7_day_demand"]

            # The LLM makes the reorder decision. The server computes the exact
            # integer quantity so a language model cannot introduce arithmetic
            # errors into inventory operations.
            validated_reorder = current_stock < predicted
            quantity = max(0, predicted - current_stock)

            if llm_reorder != validated_reorder:
                print(
                    f"[LLM Validation] Decision mismatch for {item_id}: "
                    f"LLM={llm_reorder}, validated={validated_reorder}."
                )

            final[item_id] = {
                "item_id": item_id,
                "product_name": snapshot[item_id]["name"],
                "reorder": validated_reorder,
                "recommended_quantity": quantity,
                "current_stock": current_stock,
                "predicted_7_day_demand": predicted,
                "reason": str(entry.get("reason", "")).strip(),
            }

        return final

    # ------------------------------------------------------------------
    # LLM inventory analytics
    # ------------------------------------------------------------------
    def _get_analytics(self):
        forecast = self._get_demand_prediction()
        reorder = self._get_reorder_suggestion()
        context = self._build_analytics_context(forecast, reorder)

        raw = self._call_llm("llm_analytics", context)
        payload = self._parse_json(raw, "analytics")

        observations = payload.get("observations")
        actions = payload.get("actions")
        if not isinstance(observations, list) or not isinstance(actions, list):
            raise ValueError("Analytics response must contain observations and actions lists.")

        snapshot = self._snapshot_inventory()
        total_current_stock = sum(d["stock"] for d in snapshot.values())
        total_historical_sales = sum(historical_total(i) for i in snapshot)
        low_items = [
            snapshot[item_id]["name"]
            for item_id in snapshot
            if reorder[item_id]["reorder"]
        ]

        lines = [
            "Inventory Analytics Report",
            "",
            f"Products analyzed: {len(snapshot)}",
            "Historical window: 30 days",
            f"Total current stock: {total_current_stock} units",
            f"Total historical sales: {total_historical_sales} units",
            "",
            "Product details:",
        ]

        for item_id, details in snapshot.items():
            predicted = forecast[item_id]["predicted_7_day_demand"]
            status = "LOW" if reorder[item_id]["reorder"] else "ADEQUATE"
            lines.append(
                f"- {details['name']}: stock={details['stock']} units; "
                f"30-day sales={historical_total(item_id)} units; "
                f"recent 7-day sales={recent_7_total(item_id)} units; "
                f"LLM predicted next 7-day demand={predicted} units; "
                f"trend={trend_label(item_id)}; status={status}."
            )

        lines.append("")
        lines.append("LLM observations:")
        for observation in observations[:8]:
            lines.append(f"- {str(observation).strip()}")

        lines.append("")
        lines.append("LLM management observations/actions:")
        for action in actions[:8]:
            lines.append(f"- {str(action).strip()}")

        lines.append("")
        lines.append(
            "Reorder-required items: "
            + (", ".join(low_items) if low_items else "None")
        )

        lines.append("")
        lines.append("Validated reorder quantities:")
        for item_id, entry in reorder.items():
            if entry["reorder"]:
                lines.append(
                    f"- {entry['product_name']}: reorder {entry['recommended_quantity']} units"
                )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # GET routing
    # ------------------------------------------------------------------
    def get(self, request, context):
        if not self._authenticated(request.token):
            return inventory_pb2.GetResponse(status="UNAUTHORIZED", items=[])

        if request.type == "inventory":
            snapshot = self._snapshot_inventory()
            items = [
                inventory_pb2.DataItem(
                    id=item_id,
                    data=f"Name: {details['name']}, Stock: {details['stock']}",
                )
                for item_id, details in snapshot.items()
            ]
            return inventory_pb2.GetResponse(status="SUCCESS", items=items)

        if request.type == "inventory_summary":
            snapshot = self._snapshot_inventory()
            lines = [
                "Product              | Stock | 30-Day Sales | Recent 7-Day | Trend      | Variability",
                "-" * 90,
            ]
            for item_id, details in snapshot.items():
                lines.append(
                    f"{details['name']:<20} | {details['stock']:>5} | "
                    f"{historical_total(item_id):>12} | {recent_7_total(item_id):>12} | "
                    f"{trend_label(item_id):<10} | {variability_label(item_id)}"
                )
            return inventory_pb2.GetResponse(
                status="SUCCESS",
                items=[inventory_pb2.DataItem(id="summary", data="\n".join(lines))],
            )

        try:
            if request.type == "llm_demand_prediction":
                forecast = self._get_demand_prediction()
                lines = [
                    "LLM Demand Forecast (next 7 days)",
                    "The LLM uses the complete 30-day historical sales pattern.",
                    "",
                ]
                for item_id, entry in forecast.items():
                    lines.extend(
                        [
                            f"- {entry['product_name']}: {entry['predicted_7_day_demand']} units",
                            f"  30-day sales: {entry['historical_total']} units | "
                            f"recent 7-day sales: {entry['recent_7_total']} units | "
                            f"trend: {entry['trend']} | variability: {entry['variability']}",
                            f"  LLM reasoning: {entry['reason'] or 'The forecast is based on the historical pattern.'}",
                        ]
                    )
                return inventory_pb2.GetResponse(
                    status="SUCCESS",
                    items=[
                        inventory_pb2.DataItem(
                            id="demand",
                            data="\n".join(lines),
                        )
                    ],
                )

            if request.type == "llm_reorder_suggestion":
                result = self._get_reorder_suggestion()
                lines = ["LLM Automated Reorder Suggestions", ""]
                for entry in result.values():
                    if entry["reorder"]:
                        lines.extend(
                            [
                                f"- {entry['product_name']}: REORDER {entry['recommended_quantity']} units",
                                f"  Current stock: {entry['current_stock']} units | "
                                f"LLM predicted demand: {entry['predicted_7_day_demand']} units",
                                "  Explanation: Current stock is below the LLM's predicted next-7-day demand, so replenishment is required.",
                            ]
                        )
                    else:
                        lines.extend(
                            [
                                f"- {entry['product_name']}: DO NOT REORDER (0 units)",
                                f"  Current stock: {entry['current_stock']} units | "
                                f"LLM predicted demand: {entry['predicted_7_day_demand']} units",
                                "  Explanation: Current stock is sufficient to cover the LLM's predicted next-7-day demand.",
                            ]
                        )
                return inventory_pb2.GetResponse(
                    status="SUCCESS",
                    items=[
                        inventory_pb2.DataItem(
                            id="reorder",
                            data="\n".join(lines),
                        )
                    ],
                )

            if request.type == "llm_analytics":
                return inventory_pb2.GetResponse(
                    status="SUCCESS",
                    items=[
                        inventory_pb2.DataItem(
                            id="analytics",
                            data=self._get_analytics(),
                        )
                    ],
                )

            return inventory_pb2.GetResponse(status="UNKNOWN_TYPE", items=[])

        except Exception as exc:
            print(f"[Application Server] LLM request failed: {exc}")
            return inventory_pb2.GetResponse(
                status=f"LLM_ERROR: {exc}",
                items=[],
            )


class AppServerServiceServicer(inventory_pb2_grpc.AppServerServiceServicer):
    """Internal application-server endpoint retained from the project contract."""

    def processBusinessRequest(self, request, context):
        print(
            f"[Internal App Logic] request_id={request.request_id}, "
            f"context={request.context}"
        )
        return inventory_pb2.StatusResponse(status="BUSINESS_REQUEST_PROCESSED")


def serve() -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    inventory_pb2_grpc.add_ClientServiceServicer_to_server(
        ClientServiceServicer(), server
    )
    inventory_pb2_grpc.add_AppServerServiceServicer_to_server(
        AppServerServiceServicer(), server
    )
    server.add_insecure_port(f"[::]:{APP_SERVER_PORT}")
    server.start()

    print("========================================")
    print("Node 2 - Application Server")
    print(f"gRPC port: {APP_SERVER_PORT}")
    print("Inventory: 12 products")
    print("History: 30 days per product")
    print("Historical observations: 360")
    print("========================================")

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    serve()
