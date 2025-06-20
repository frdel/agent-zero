# Use the pre-built base image for A0
# FROM agent-zero-base:local
FROM frdel/agent-zero-base:latest

# Check if the argument is provided, else throw an error
ARG BRANCH
RUN if [ -z "$BRANCH" ]; then echo "ERROR: BRANCH is not set!" >&2; exit 1; fi
ENV BRANCH=$BRANCH

# Initialize and update git submodules first
# This assumes that the Docker build context itself is a git repository
# or that the source code (including .git) is copied before this step.
# If install_A0.sh clones the repo, this might be better placed inside that script
# or after the repo is available. For now, placing it early.
# A common pattern is to COPY the repo first, then run submodule update.
# Let's assume the repo is copied by /ins/pre_install.sh or install_A0.sh from $BRANCH
# So, this needs to run *after* the code is in /a0.
# Re-evaluating: The COPY ./fs/ / command copies scripts, not the main repo.
# The main repo is likely cloned in install_A0.sh.
# So, submodule update should happen *after* install_A0.sh and *inside* the repo dir.

# Copy contents of the project to /a0
COPY ./fs/ /

# pre installation steps
RUN bash /ins/pre_install.sh $BRANCH

# install A0
RUN bash /ins/install_A0.sh $BRANCH

# Update submodules after A0 main code is cloned/installed
# Assuming Agent Zero code is in /a0
RUN cd /a0 && git submodule update --init --recursive

# install additional software
RUN bash /ins/install_additional.sh $BRANCH

# Install Node.js and npm
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs

# cleanup repo and install A0 without caching, this speeds up builds
ARG CACHE_DATE=none
RUN echo "cache buster $CACHE_DATE" && bash /ins/install_A02.sh $BRANCH

# Build the React application in audit-ai-ecommerce
# This assumes install_A02.sh or previous steps ensure /a0/audit-ai-ecommerce exists
RUN echo "Building audit-ai-ecommerce frontend..." && \
    cd /a0/audit-ai-ecommerce && \
    npm install && \
    npm run build && \
    echo "Finished building audit-ai-ecommerce frontend."

# post installation steps
RUN bash /ins/post_install.sh $BRANCH

# Expose ports
EXPOSE 22 80 9000-9009

RUN chmod +x /exe/initialize.sh /exe/run_A0.sh /exe/run_searxng.sh /exe/run_tunnel_api.sh

# initialize runtime and switch to supervisord
CMD ["/exe/initialize.sh", "$BRANCH"]
