#!/bin/bash
# copy_shared.sh — Run before every docker build
# Copies shared files into each service's src/ directory

cp shared/mock_data.py orchestrator/src/mock_data.py
cp shared/a2a_models.py orchestrator/src/a2a_models.py
cp shared/mock_data.py recruitment-agent/src/mock_data.py
cp shared/a2a_models.py recruitment-agent/src/a2a_models.py
cp shared/mock_data.py employee-services/src/mock_data.py
cp shared/a2a_models.py employee-services/src/a2a_models.py
cp shared/mock_data.py analytics-agent/src/mock_data.py
cp shared/a2a_models.py analytics-agent/src/a2a_models.py

echo "Shared files copied to all services."
