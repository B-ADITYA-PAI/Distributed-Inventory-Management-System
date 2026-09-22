#!/bin/bash
set -e
python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. inventory.proto
echo "Generated inventory_pb2.py and inventory_pb2_grpc.py"