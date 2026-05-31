# Use official LTS Jenkins base image with JDK 17
FROM jenkins/jenkins:lts-jdk17

# Switch to root user to allow system level package installation
USER root

# Update repositories and install the native Linux Docker CLI binary
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

# Drop privileges back to the standard jenkins user context
USER jenkins

# Automated Plugin Provisioning for GitOps (JCasC & Job DSL)
RUN jenkins-plugin-cli --plugins configuration-as-code job-dsl