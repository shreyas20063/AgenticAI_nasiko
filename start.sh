#!/bin/bash
set -e

echo "=== Nasiko HR Automation — Local Setup ==="

# Check .env exists and has API key
if [ ! -f .env ]; then
  echo "ERROR: .env file not found. Run: cp .env.example .env and set your OPENAI_API_KEY."
  exit 1
fi

if grep -q "sk-your-key-here" .env; then
  echo "ERROR: Please set a real OPENAI_API_KEY in .env"
  exit 1
fi

# Create Docker network (ignore error if already exists)
echo "Creating Docker network..."
docker network create agents-net 2>/dev/null || echo "Network 'agents-net' already exists, skipping."

# Copy shared files into each agent's build context
echo "Copying shared files..."
bash copy_shared.sh

# Build and start all services
echo "Building and starting all services..."
docker compose up --build -d

# Wait for orchestrator to be healthy
echo "Waiting for services to be ready..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:5000/health > /dev/null 2>&1; then
    echo ""
    echo "All services are up!"
    echo ""
    echo "  Orchestrator: http://localhost:5000"
    echo "  Health check: http://localhost:5000/health"
    echo "  Agent card:   http://localhost:5000/.well-known/agent.json"
    echo ""
    echo "Test with:"
    echo "  curl -X POST http://localhost:5000/ \\"
    echo "    -H 'Content-Type: application/json' \\"
    echo "    -d '{\"jsonrpc\":\"2.0\",\"id\":\"1\",\"method\":\"message/send\",\"params\":{\"message\":{\"role\":\"user\",\"parts\":[{\"kind\":\"text\",\"text\":\"Role: EMPLOYEE (EMP-001). What is the remote work policy?\"}]}}}'"
    exit 0
  fi
  printf "."
  sleep 3
done

echo ""
echo "Services did not become healthy in time. Check logs with: docker compose logs"
exit 1
