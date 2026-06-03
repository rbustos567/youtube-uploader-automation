# Use official LTS Jenkins base image with JDK 17
FROM jenkins/jenkins:lts-jdk17

# Switch to root user to allow system level package installation
USER root

# Update repositories and install the native Linux Docker CLI binary
#RUN apt-get update && apt-get install -y --no-install-recommends \
#    docker.io \
#    && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y docker.io && rm -rf /var/lib/apt/lists/*

# Drop privileges back to the standard jenkins user context
USER jenkins

# Disable the interactive web setup wizard for seamless GitOps boots
ENV JAVA_OPTS="-Djenkins.install.runSetupWizard=false"

# Automated Plugin Provisioning for GitOps (JCasC, Job DSL & Pipelines)
RUN jenkins-plugin-cli --plugins \
    configuration-as-code \
    job-dsl \
    workflow-aggregator \
    git

# OFFLINE PLUGINS INJECTION (Bypasses Jenkins Infrastructure Downtime)
COPY --chown=jenkins:jenkins *.hpi /usr/share/jenkins/ref/plugins/