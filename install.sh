#!/bin/bash

echo "===================================================="
echo "   YOUTUBE AUTOMATION SYSTEM - ARCHITECTURE INSTALLER "
echo "===================================================="

# 1. ENVIRONMENT DETECTION & PREREQUISITES VERIFICATION
echo ""
echo "[1/4] Verifying and installing system prerequisites..."

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
    echo "[FATAL] Unsupported Linux distribution. No compatible package manager found (apt|dnf|yum)."
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
            
            # Setup official stable repository for RedHat-based ecosystems
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
# 2. LOCAL ENVIRONMENT MANAGEMENT (.env)
# ==============================================================================
echo ""
echo "[2/4] Setting up localized environment variables..."

if [ ! -f .env ]; then
    echo "[INFO] No .env file detected. Generating from template..."
    if [ -f .env.example ]; then
        cp .env.example .env
        
        # Inject dynamic host project context absolute path
        CURRENT_WORKSPACE_DIR=$(pwd)
        sed -i "s|DEPLOY_WORKSPACE_PATH=|DEPLOY_WORKSPACE_PATH=${CURRENT_WORKSPACE_DIR}|g" .env
        
        echo "Please configure your interactive variables now:"
        read -p "Enter your notification target email: " TARGET_USER_EMAIL
        sed -i "s|NOTIFICATION_EMAIL=user@example.com|NOTIFICATION_EMAIL=${TARGET_USER_EMAIL}|g" .env
        
        echo "[SUCCESS] Localized .env file generated cleanly."
    else
        echo "[ERROR] Critical configuration template '.env.example' missing from repository repository."
        exit 1
    fi
else
    echo "[OK] Existing .env file detected. Retaining current infrastructure runtime values."
fi

# Export configuration properties to shell context execution environment
export $(grep -v '^#' .env | xargs)


# ==============================================================================
# 3. LOCAL FILESYSTEM STRUCTURE VERIFICATION
# ==============================================================================
echo ""
echo "[3/4] Ensuring local filesystem integrity..."

# Enforce target directory architecture generation for volume bindings
mkdir -p data config jenkins_home
echo "[OK] Data, Config, and Jenkins directory trees verified."

# Run critical security validation for required Google API OAuth2 secrets
if [ ! -f config/client_secrets.json ]; then
    echo "[WARNING] 'config/client_secrets.json' target file not found."
    echo "Remember to place your Google Cloud API OAuth2 credentials inside the './config' folder before launching automation jobs."
fi


# ==============================================================================
# 4. MICROSERVICES CONTAINER MESH LAUNCH (DEPLOYMENT)
# ==============================================================================
echo ""
echo "[4/4] Launching containerized microservices layer..."

echo "Building custom engine images and initializing isolated Docker network topology..."
docker compose up -d --build

if [ $? -eq 0 ]; then
    echo ""
    echo "===================================================="
    echo "   DEPLOYMENT COMPLETED SUCCESSFULLY!"
    echo "===================================================="
    echo "Jenkins automation server running at: http://localhost:8080"
    echo "Notification metrics pipeline targeted to: ${NOTIFICATION_EMAIL}"
    echo "All workflow logs are persistent inside: ./jenkins_home and ./data"
else
    echo "[FATAL] Docker Compose failed to spin up the container network orchestration layer."
    exit 1
fi