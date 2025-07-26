# Agent Zero + LM Studio Docker Setup

This setup allows you to run Agent Zero with LM Studio for 24/7 operation using local models.

## 🚀 Quick Start

1. **Run the setup script:**
   ```bash
   ./scripts/setup-lmstudio.sh
   ```

2. **Install and configure LM Studio:**
   - Download LM Studio from [https://lmstudio.ai/](https://lmstudio.ai/)
   - Download recommended models (see `configs/lmstudio-models.json`)
   - Start LM Studio server on port 1234

3. **Update configuration:**
   - Edit `.env` file with your model names
   - Adjust settings based on your hardware

4. **Start services:**
   ```bash
   ./scripts/setup-lmstudio.sh --start
   ```

5. **Access Agent Zero:**
   - Web UI: http://localhost:50080
   - LM Studio API: http://localhost:1234

## 📋 Requirements

### Hardware Requirements
- **Minimum:** 8GB RAM, 6GB VRAM
- **Recommended:** 16GB RAM, 12GB VRAM
- **Optimal:** 32GB RAM, 24GB+ VRAM

### Software Requirements
- Docker & Docker Compose
- NVIDIA Docker (for GPU acceleration)
- LM Studio

## 🔧 Configuration

### Model Configurations

We provide three pre-configured setups:

#### Low Resource (8GB VRAM)
- Chat: Mistral 7B Instruct
- Utility: Mistral 7B Instruct
- Embedding: Nomic Embed Text v1.5

#### Balanced (12-16GB VRAM)
- Chat: Llama 3.1 8B Instruct
- Utility: Qwen2.5 7B Instruct
- Embedding: BGE Large EN v1.5

#### High Performance (48GB+ VRAM)
- Chat: Llama 3.1 70B Instruct
- Utility: Llama 3.1 8B Instruct
- Embedding: BGE Large EN v1.5

### Environment Variables

Key settings in `.env`:

```bash
# LM Studio Connection
LM_STUDIO_BASE_URL=http://lmstudio:1234/v1

# Model Names (update these to match your LM Studio models)
CHAT_MODEL_NAME=llama-3.1-8b-instruct
UTIL_MODEL_NAME=llama-3.1-8b-instruct
EMBED_MODEL_NAME=nomic-embed-text-v1.5

# Performance Settings
CHAT_MODEL_CTX_LENGTH=32768
CHAT_MODEL_TEMPERATURE=0.7
```

## 🐳 Docker Services

The setup includes:

1. **LM Studio Container:** Runs LM Studio server with GPU support
2. **Agent Zero Container:** Main Agent Zero application
3. **Watchtower:** Automatic updates (optional)

### Service Management

```bash
# Start services
docker-compose -f docker/lmstudio/docker-compose.yml up -d

# Stop services
docker-compose -f docker/lmstudio/docker-compose.yml down

# View logs
docker-compose -f docker/lmstudio/docker-compose.yml logs -f

# Restart specific service
docker-compose -f docker/lmstudio/docker-compose.yml restart agent-zero
```

## 🔍 Troubleshooting

### Common Issues

1. **Connection refused to LM Studio:**
   - Ensure LM Studio is running on port 1234
   - Check firewall settings
   - Verify model is loaded in LM Studio

2. **Model not found:**
   - Check model names in `.env` match LM Studio exactly
   - Ensure models are loaded and running in LM Studio

3. **Out of memory errors:**
   - Use smaller models or reduce context length
   - Check available VRAM with `nvidia-smi`

4. **Slow performance:**
   - Reduce context length
   - Use quantized models (Q4_K_M recommended)
   - Ensure GPU acceleration is working

### Health Checks

The setup includes automatic health checks:
- LM Studio API availability
- Agent Zero web interface
- Container resource usage

### Monitoring

View real-time logs:
```bash
# All services
docker-compose -f docker/lmstudio/docker-compose.yml logs -f

# Specific service
docker-compose -f docker/lmstudio/docker-compose.yml logs -f agent-zero
```

## 🔧 Advanced Configuration

### Custom Models

To use custom models:

1. Add model to LM Studio
2. Update model name in `.env`
3. Restart Agent Zero container

### Resource Limits

Adjust Docker resource limits in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      memory: 16G
      cpus: '8'
```

### Persistent Storage

Data is stored in Docker volumes:
- `agent_zero_data`: Main application data
- `agent_zero_memory`: Agent memory
- `agent_zero_knowledge`: Knowledge base
- `lmstudio_models`: Downloaded models

## 📚 Additional Resources

- [LM Studio Documentation](https://lmstudio.ai/docs)
- [Agent Zero Documentation](../../docs/README.md)
- [Model Recommendations](../../configs/lmstudio-models.json)

## 🆘 Support

If you encounter issues:

1. Check the troubleshooting section above
2. Review logs for error messages
3. Ensure your hardware meets requirements
4. Join the Agent Zero Discord for community support
