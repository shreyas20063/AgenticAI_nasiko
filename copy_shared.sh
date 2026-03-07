#!/bin/bash
# copy_shared.sh — copies shared files into each agent's src/ before docker build
set -e

for dir in orchestrator recruitment-agent employee-services analytics-agent; do
    cp shared/mock_data.py "$dir/src/mock_data.py"
    cp shared/a2a_models.py "$dir/src/a2a_models.py"
    echo "Copied shared files to $dir/src/"
done

echo "All shared files copied. Ready for docker compose build."
