#!/bin/bash

# Agent Zero LM Studio Setup Script
# This script helps set up Agent Zero with LM Studio for 24/7 operation

set -e

echo "🚀 Agent Zero LM Studio Setup"
echo "=============================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker is installed
check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    print_success "Docker and Docker Compose are installed"
}

# Check if NVIDIA Docker is available (for GPU support)
check_nvidia_docker() {
    if command -v nvidia-docker &> /dev/null || docker info | grep -q nvidia; then
        print_success "NVIDIA Docker support detected"
        return 0
    else
        print_warning "NVIDIA Docker support not detected. GPU acceleration will not be available."
        return 1
    fi
}

# Create necessary directories
create_directories() {
    print_status "Creating necessary directories..."
    
    mkdir -p docker/lmstudio/agent-config
    mkdir -p docker/lmstudio/lmstudio-config
    
    print_success "Directories created"
}

# Copy configuration files
setup_config() {
    print_status "Setting up configuration files..."
    
    # Copy environment file
    if [ ! -f ".env" ]; then
        cp docker/lmstudio/lmstudio.env .env
        print_success "Environment file created (.env)"
    else
        print_warning "Environment file (.env) already exists. Please review and update manually."
    fi
    
    # Create agent config directory structure
    mkdir -p docker/lmstudio/agent-config
    
    print_success "Configuration setup complete"
}

# Function to select configuration based on system resources
select_configuration() {
    print_status "Detecting system configuration..."
    
    # Try to detect available VRAM (this is a simple heuristic)
    if command -v nvidia-smi &> /dev/null; then
        VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
        print_status "Detected ${VRAM}MB VRAM"
        
        if [ "$VRAM" -lt 8192 ]; then
            CONFIG="low_resource"
            print_warning "Low VRAM detected. Using low resource configuration."
        elif [ "$VRAM" -lt 24576 ]; then
            CONFIG="balanced"
            print_status "Medium VRAM detected. Using balanced configuration."
        else
            CONFIG="high_performance"
            print_status "High VRAM detected. Using high performance configuration."
        fi
    else
        print_warning "Could not detect GPU. Using balanced configuration."
        CONFIG="balanced"
    fi
    
    echo "Selected configuration: $CONFIG"
    echo "Please review configs/lmstudio-models.json for model recommendations."
}

# Start services
start_services() {
    print_status "Starting Agent Zero with LM Studio..."
    
    cd docker/lmstudio
    
    # Pull latest images
    print_status "Pulling latest Docker images..."
    docker-compose pull
    
    # Start services
    print_status "Starting services..."
    docker-compose up -d
    
    print_success "Services started!"
    print_status "Agent Zero will be available at: http://localhost:50080"
    print_status "LM Studio API will be available at: http://localhost:1234"
}

# Check service health
check_health() {
    print_status "Checking service health..."
    
    sleep 10
    
    # Check if containers are running
    if docker-compose -f docker/lmstudio/docker-compose.yml ps | grep -q "Up"; then
        print_success "Services are running"
    else
        print_error "Some services failed to start. Check logs with: docker-compose -f docker/lmstudio/docker-compose.yml logs"
        exit 1
    fi
}

# Main execution
main() {
    echo "Starting setup process..."
    
    check_docker
    check_nvidia_docker
    create_directories
    setup_config
    select_configuration
    
    echo ""
    echo "Setup complete! Next steps:"
    echo "1. Install LM Studio from https://lmstudio.ai/"
    echo "2. Download recommended models (see configs/lmstudio-models.json)"
    echo "3. Start LM Studio server on port 1234"
    echo "4. Update model names in .env file"
    echo "5. Run this script with --start to launch services"
    echo ""
    
    if [ "$1" = "--start" ]; then
        start_services
        check_health
        
        echo ""
        print_success "🎉 Agent Zero with LM Studio is now running!"
        echo "Access the web interface at: http://localhost:50080"
        echo ""
        echo "To stop services: docker-compose -f docker/lmstudio/docker-compose.yml down"
        echo "To view logs: docker-compose -f docker/lmstudio/docker-compose.yml logs -f"
    fi
}

# Run main function with all arguments
main "$@"
