#!/bin/bash

echo "===================================================="
echo "   YOUTUBE AUTOMATION SYSTEM - ARCHITECTURE INSTALLER "
echo "===================================================="

# ==============================================================================
# 1. LOCAL ENVIRONMENT MANAGEMENT & STRICT VALIDATION (FAIL-FAST)
# ==============================================================================
echo ""
echo "[1/4] Setting up and validating environment configuration..."

if [ ! -f .env ]; then
    echo "[INFO] No .env file detected. Generating from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        
        # Inject dynamic host project context absolute path
        CURRENT_WORKSPACE_DIR=$(pwd)
        sed -i "s|DEPLOY_WORKSPACE_PATH=|DEPLOY_WORKSPACE_PATH=${CURRENT_WORKSPACE_DIR}|g" .env
        
        echo "----------------------------------------------------"
        echo "   INTERACTIVE ENVIRONMENT INITIALIZATION           "
        echo "----------------------------------------------------"
        # Prompt for pipeline settings
        read -p "Enter your notification target email: " TARGET_USER_EMAIL
        sed -i "s|NOTIFICATION_EMAIL=user@example.com|NOTIFICATION_EMAIL=${TARGET_USER_EMAIL}|g" .env
        
        # Secure prompt for custom administrative credentials
        read -p "Create your Jenkins Admin Username [admin]: " SECURE_ADMIN_USER
        SECURE_ADMIN_USER=${SECURE_ADMIN_USER:-admin} # Fallback to 'admin' if user hits Enter
        sed -i "s|JENKINS_INITIAL_ADMIN_USER=|JENKINS_INITIAL_ADMIN_USER=${SECURE_ADMIN_USER}|g" .env
        
        # Read password silently so it's not exposed on the terminal screen
        read -s -p "Create your Jenkins Admin Password: " SECURE_ADMIN_PASS
        echo "" # New line for terminal aesthetics
        sed -i "s|JENKINS_INITIAL_ADMIN_PASSWORD=|JENKINS_INITIAL_ADMIN_PASSWORD=${SECURE_ADMIN_PASS}|g" .env
        
        echo "[SUCCESS] Localized secure .env file generated cleanly."
        echo "----------------------------------------------------"
    else
        echo "[ERROR] Critical configuration template '.env.example' missing from repository."
        exit 1
    fi
else
    echo "[OK] Existing .env file detected. Evaluating variable criteria..."
fi

# Load environmental values safely into active subshell memory context
export $(grep -v '^#' .env | xargs)

# Assertion framework to guarantee execution correctness before deployment
MISSING_VARS=0

validate_variable() {
    local VAR_NAME=$1
    local VAR_VALUE=${!VAR_NAME}
    
    if [ -z "$VAR_VALUE" ]; then
        echo "[ERROR] Mandatory configuration variable '${VAR_NAME}' is empty or undefined inside .env"
        MISSING_VARS=$((MISSING_VARS + 1))
    fi
}

# Run assertion suite across target architecture keys
validate_variable "NOTIFICATION_EMAIL"
validate_variable "OLLAMA_HOST_URL"
validate_variable "OLLAMA_MODEL_NAME"
validate_variable "SYSTEM_TIMEZONE"
validate_variable "PIPELINE_CRON_SCHEDULE"
validate_variable "JENKINS_INITIAL_ADMIN_USER"
validate_variable "JENKINS_INITIAL_ADMIN_PASSWORD"
validate_variable "JENKINS_PROJECT_NAME"
validate_variable "JENKINS_GITHUB_REPO_URL"
validate_variable "DEPLOY_WORKSPACE_PATH"


if [ "$MISSING_VARS" -ne 0 ]; then
    echo "[FATAL] Environment validation failed with ${MISSING_VARS} unresolved errors. Aborting installer."
    exit 1
else
    echo "[OK] All required environment criteria validated successfully."
fi


# ==============================================================================
# 2. ENVIRONMENT DETECTION & PREREQUISITES VERIFICATION
# ==============================================================================
echo ""
echo "[2/4] Verifying and installing system prerequisites..."

# Validate execution privileges
if [ "$EUID" -ne 0 ]; then
    echo "[INFO] This installer requires root privileges to verify or install Docker."
    echo "Please run this script using: sudo ./install.sh"
    exit 1
fi

# Detect host operating system package manager dynamically
if command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt"
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
elif command -v yum &> /dev/null; then
    PKG_MANAGER="yum"
else
    echo "[FATAL] Unsupported Linux distribution. No compatible package manager found (APT/DNF/YUM)."
    exit 1
fi

echo "[OK] Detected package manager: ${PKG_MANAGER^^}"

# Internal routine to install Docker engine based on package manager topology
install_docker_native() {
    case "$PKG_MANAGER" in
        apt)
            echo "[INFO] Initializing official Docker installation via APT..."
            apt-get update -y
            apt-get install -y ca-certificates curl gnupg lsb-release
            
            mkdir -p /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg --yes
            
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
            
            apt-get update -y
            apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        dnf|yum)
            echo "[INFO] Initializing official Docker installation via ${PKG_MANAGER^^}..."
            $PKG_MANAGER install -y dnf-plugins-core
            
            dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo &> /dev/null || \
            yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo &> /dev/null
            
            $PKG_MANAGER update -y
            $PKG_MANAGER install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
    esac
}

# Verify if Docker system engine binary is present on the host
if ! command -v docker &> /dev/null; then
    install_docker_native
else
    echo "[OK] Docker engine is already installed."
fi

# Verify if Docker Compose V2 plugin is integrated within the engine context
if ! docker compose version &> /dev/null; then
    echo "[INFO] Docker Compose V2 plugin not detected. Resolving dependency..."
    case "$PKG_MANAGER" in
        apt)
            apt-get update -y
            apt-get install -y docker-compose-plugin
            ;;
        dnf|yum)
            $PKG_MANAGER update -y
            $PKG_MANAGER install -y docker-compose-plugin
            ;;
    esac
    echo "[OK] Docker Compose V2 plugin integrated successfully."
else
    echo "[OK] Docker Compose V2 plugin is already installed."
fi

# Manage service lifecycle daemon on the host system
systemctl enable docker
systemctl start docker


# ==============================================================================
# 3. LOCAL FILESYSTEM STRUCTURE & API TOKEN VERIFICATION
# ==============================================================================
echo ""
echo "[3/4] Ensuring local filesystem and API credentials integrity..."

# Always ensure directory skeletons exist first
mkdir -p data config jenkins_home
echo "[OK] Data, Config, and Jenkins directory trees verified."

# Strict rule validation for YouTube API Access
if [ ! -f config/token.json ]; then
    echo "----------------------------------------------------------------------"
    echo "[FATAL] Missing YouTube OAuth2 API execution token!"
    echo "The automation core requires 'config/token.json' to modify and upload videos."
    echo "Please place your pre-generated token inside the './config' folder."
    echo "----------------------------------------------------------------------"
    exit 1
else
    echo "[OK] YouTube API authentication token 'config/token.json' detected."
fi


# ==============================================================================
# 4. MICROSERVICES CONTAINER MESH LAUNCH & LLM PROVISIONING
# ==============================================================================
echo ""
echo "[4/4] Launching containerized microservices layer..."

echo "Building custom engine images and initializing isolated Docker network topology..."
docker compose up -d --build

if [ $? -eq 0 ]; then
    echo "[OK] Container mesh generated successfully."
    
    echo "Verifying local LLM availability inside Ollama container..."
    echo "[INFO] Target model configured: ${OLLAMA_MODEL_NAME}"
    
    # Grace period for the Ollama daemon process initialization inside the mesh
    sleep 3
    
    if docker exec ollama-service ollama list | grep -q "${OLLAMA_MODEL_NAME}"; then
        echo "[OK] Model '${OLLAMA_MODEL_NAME}' is already cached and ready to use."
    else
        echo "[INFO] Model '${OLLAMA_MODEL_NAME}' not found locally. Initializing automated pull sequence..."
        echo "Please wait, downloading model weights inside the container..."
        
        docker exec -it ollama-service ollama pull "${OLLAMA_MODEL_NAME}"
        
        if [ $? -eq 0 ]; then
            echo "[OK] Model '${OLLAMA_MODEL_NAME}' downloaded and provisioned successfully."
        else
            echo "[WARNING] Failed to pull model '${OLLAMA_MODEL_NAME}'."
        fi
    fi

    echo ""
    echo "===================================================="
    echo "   DEPLOYMENT COMPLETED SUCCESSFULLY!"
    echo "===================================================="
    echo "Jenkins automation server running at: http://localhost:8080"
    echo "Notification metrics pipeline targeted to: ${NOTIFICATION_EMAIL}"
    echo "AI Automation Engine backed by: Ollama (${OLLAMA_MODEL_NAME})"
    echo "All workflow logs are persistent inside: ./jenkins_home and ./data"
else
    echo "[FATAL] Docker Compose failed to spin up the container network orchestration layer."
    exit 1
fi