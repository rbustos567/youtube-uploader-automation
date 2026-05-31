#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "===================================================="
echo "   YOUTUBE AUTOMATION SYSTEM - ARCHITECTURE INSTALLER"
echo "===================================================="

# ---------------------------------------------------------
# [1/4] Environment Pre-flight Checks and Validations
# ---------------------------------------------------------
echo ""
echo "[1/4] Setting up and validating environment configuration..."

# Critical Check: Verify the existence of the template (env.example or .env.example)
if [ ! -f ".env.example" ] && [ ! -f "env.example" ]; then
    echo "[ERROR] Critical configuration template '.env.example' or 'env.example' missing from repository."
    exit 1
fi

# Standardize template name to .env.example if it was named env.example
if [ ! -f ".env.example" ] && [ -f "env.example" ]; then
    echo "[INFO] Standardizing template name from 'env.example' to '.env.example'..."
    mv env.example .env.example
fi

# Generate local execution .env file if it does not exist
if [ ! -f ".env" ]; then
    echo "[INFO] No .env file detected. Generating from template..."
    cp .env.example .env
    
    # Dynamic deployment path discovery via PWD
    current_dir=$(pwd)
    if grep -q "DEPLOY_WORKSPACE_PATH=" .env; then
        sed -i "s|DEPLOY_WORKSPACE_PATH=.*|DEPLOY_WORKSPACE_PATH=${current_dir}|" .env
    else
        echo "DEPLOY_WORKSPACE_PATH=${current_dir}" >> .env
    fi
    echo "[OK] Generated .env file with dynamic local path injection."
else
    echo "[OK] Existing .env file detected. Evaluating variable criteria..."
fi

# ---------------------------------------------------------
# [2/4] Directory Infrastructure & Runtime Dependencies
# ---------------------------------------------------------
echo ""
echo "[2/4] Establishing local data persistence layers..."

# Create standard host volume bindings for container persistence
mkdir -p data/jenkins_home
mkdir -p data/ollama_storage
mkdir -p config

# Enforce secure permission boundaries for Jenkins (UID 1000 standard)
chmod -R 755 data/
chown -R 1000:1000 data/jenkins_home

# Verify OAuth2 Google Application Credentials layout before spinning up services
if [ ! -f "config/token.json" ]; then
    echo "[WARN] OAuth2 client state 'config/token.json' not found."
    echo "[WARN] Ensure Google Video API tokens are placed in the config mount to prevent execution blocks."
else
    echo "[OK] Core runtime credentials present inside configuration mount."
fi

# ---------------------------------------------------------
# [3/4] Container Mesh Orchestration (Docker Compose)
# ---------------------------------------------------------
echo ""
echo "[3/4] Deploying isolated service layer mesh via Docker Compose..."

# Safely source operational variables line by line, ignoring comments and blanks
while IFS= read -r line || [ -n "$line" ]; do
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ -z "$line" ]] && continue
    if [[ "$line" == *=* ]]; then
        export "$line"
    fi
done < .env

# Execute build phase and run the decoupled microservice graph in detached mode
if ! docker compose up -d --build; then
    echo "[FATAL] Docker Compose failed to spin up the container network orchestration layer."
    exit 1
fi

echo "[OK] Container mesh generated successfully."

# ---------------------------------------------------------
# [4/4] Asynchronous Health Check & Model Ingestion (Ollama)
# ---------------------------------------------------------
echo ""
echo "[4/4] Verifying local LLM availability inside Ollama container..."

# INFALLIBLE BUGFIX: Query Docker Compose directly to get the actual running container name
echo "[INFO] Resolving Ollama container identity..."
ollama_container=$(docker compose ps --format "table {{.Name}}" | grep "ollama-service" | xargs)

if [ -z "${ollama_container}" ]; then
    echo "[FATAL] Could not resolve Ollama container name. Is the service running?"
    exit 1
fi

# Target LLM configuration fetched from .env (defaults to gemma2:9b if empty)
target_model="${OLLAMA_MODEL_NAME:-gemma2:9b}"
echo "[INFO] Target container resolved: ${ollama_container}"
echo "[INFO] Target model configured: ${target_model}"

# --- Async API Gateway Wait-Loop ---
echo "[INFO] Waiting for Ollama engine API layer to become responsive..."
max_retries=15
counter=0

until docker exec "${ollama_container}" ollama list > /dev/null 2>&1; do
    counter=$((counter + 1))
    if [ $counter -gt $max_retries ]; then
        echo "[FATAL] Timeout reached. Ollama API failed to initialize within expected window."
        echo "[FATAL] Please check 'docker logs ${ollama_container}' for internal faults."
        exit 1
    fi
    echo "[WAIT] API initialization in progress... (Attempt ${counter}/${max_retries})"
    sleep 3
done

# --- Safe Model Validation and Hot Ingestion Sequence ---
if docker exec "${ollama_container}" ollama list | grep -q "${target_model}"; then
    echo "[OK] Model '${target_model}' is already cached and ready to use."
else
    echo "[INFO] Model '${target_model}' not found locally inside container. Initializing pull sequence..."
    
    if ! docker exec -it "${ollama_container}" ollama pull "${target_model}"; then
        echo "[ERROR] Failed to pull model weights for '${target_model}'."
        echo "[WARN] Continuing setup, but you must manually trigger 'ollama pull ${target_model}' inside the container."
    else
        echo "[OK] Model '${target_model}' successfully ingested into the container layer."
    fi
fi

# ---------------------------------------------------------
# Deployment Summary Output
# ---------------------------------------------------------
echo ""
echo "===================================================="
echo "        DEPLOYMENT COMPLETED SUCCESSFULLY!"
echo "===================================================="
echo " Jenkins automation server running at: http://localhost:9090"
echo " Notification metrics pipeline targeted to: ${NOTIFICATION_EMAIL}"
echo " AI Automation Engine backed by: Ollama (${target_model})"
echo " All workflow logs are persistent inside ./data/jenkins_home and ./data/"
echo "===================================================="