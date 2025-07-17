# OpenRAG Ansible Deployment

This directory contains Ansible playbooks and scripts to automatically set up the OpenRAG environment on one or more servers.

## Features

- **Automated Docker installation** 
- **NVIDIA GPU support**
- **Complete OpenRAG deployment**
- **Multi-server support**

## Quick Start

### 1. Prerequisites

- Ansible installed on your control machine
- SSH access to target servers (if deploying remotely)
- Ubuntu 20.04+ or similar Linux distribution on target servers

### 2. Local Deployment (Easiest)

```bash
cd ansible/
./deploy.sh
# Choose option 1: "Deploy to local machine (simple)"
```

### 3. Remote Deployment

1. **Edit the inventory file:**
   ```bash
   # For simple deployment
   nano inventory.ini
   
   # For GPU/CPU distinction
   nano inventory-gpu-cpu.ini
   ```

2. **Add your servers:**
   ```ini
   [openrag_servers]
   server1 ansible_host=192.168.1.100 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa
   server2 ansible_host=192.168.1.101 ansible_user=ubuntu ansible_ssh_private_key_file=~/.ssh/id_rsa
   ```

3. **Run the deployment:**
   ```bash
   ./deploy.sh
   # Choose option 2: "Deploy with GPU/CPU distinction (advanced)"
   ```

## Files Overview

### Playbooks

- **`playbook.yml`** - Simple deployment for all servers (auto-detects GPU)
- **`playbook-gpu-cpu.yml`** - Advanced deployment with GPU/CPU server distinction

### Inventory Files

- **`inventory.ini`** - Simple inventory for basic deployment
- **`inventory-gpu-cpu.ini`** - Advanced inventory with GPU/CPU groups

### Configuration

- **`ansible.cfg`** - Ansible configuration settings

### Scripts

- **`deploy.sh`** - Interactive deployment and management script

## Deployment Options

### Option 1: Simple Deployment (`playbook.yml`)

- Automatically detects NVIDIA GPUs
- Installs NVIDIA drivers if GPU detected
- Single playbook for all server types
- Good for small deployments

### Option 2: Advanced Deployment (`playbook-gpu-cpu.yml`)

- Separate groups for GPU and CPU servers
- Optimized configurations for each type
- Better for larger, mixed environments
- Allows different compose profiles

## Manual Deployment

If you prefer to run Ansible commands directly:

### Simple Deployment
```bash
ansible-playbook -i inventory.ini playbook.yml --ask-become-pass
```

### Advanced Deployment
```bash
ansible-playbook -i inventory-gpu-cpu.ini playbook-gpu-cpu.yml --ask-become-pass
```

### Check Status
```bash
ansible all -i inventory.ini -m shell -a "docker ps" --become
```

## Service Management

The deployment script provides several management options:

### Check Status
```bash
./deploy.sh status
```

### Stop Services
```bash
./deploy.sh stop
```

### Start Services
```bash
./deploy.sh start
```

### View Logs
```bash
./deploy.sh logs [service_name]
```

### Update Deployment
```bash
./deploy.sh update
```

## What Gets Installed

### System Packages
- Docker CE with Compose plugin
- NVIDIA drivers (if GPU detected)
- NVIDIA Container Toolkit
- Python 3 and pip
- Essential development tools

### OpenRAG Components
- Complete OpenRAG codebase
- All required Python dependencies
- Docker containers for:
  - OpenRAG API server
  - Milvus vector database
  - PostgreSQL database
  - Optional: vLLM inference server

### Directory Structure
```
/home/[user]/openrag/
├── data/           # Document storage
├── db/             # Database files
├── logs/           # Application logs
├── model_weights/  # Cached model files
├── .env            # Environment configuration
└── ...             # OpenRAG source code
```

## Configuration

### Environment Variables

The deployment automatically creates a `.env` file from `.env.example`. Key variables to customize:

```bash
# LLM Configuration
BASE_URL=http://your-llm-endpoint
API_KEY=your-api-key
MODEL=your-model-name

# Application Settings
APP_PORT=8080
RETRIEVER_TOP_K=20

# Embedder Settings
EMBEDDER_MODEL_NAME=Qwen/Qwen3-Embedding-0.6B
```

### Inventory Variables

You can set variables in your inventory file:

```ini
[openrag_servers:vars]
nvidia_driver_version=535
project_user=ubuntu
project_path=/opt/openrag
```

## Troubleshooting

### Common Issues

1. **Docker permission denied**
   ```bash
   # Re-login to apply docker group membership
   sudo su - $USER
   ```

2. **NVIDIA driver installation fails**
   ```bash
   # Check GPU compatibility
   lspci | grep -i nvidia
   ```

3. **Services not starting**
   ```bash
   # Check logs
   docker compose logs
   ```

### Manual Recovery

If something goes wrong, you can manually clean up:

```bash
# Stop all containers
docker compose down

# Remove containers and images
docker system prune -a

# Re-run deployment
./deploy.sh
```

## Security Considerations

- Change default passwords in `.env` file
- Use SSH key authentication for remote servers
- Configure firewall rules for exposed ports:
  - 8080: OpenRAG API
  - 8265: Ray Dashboard (optional)
  - 19530: Milvus (internal only)

## Advanced Usage

### Custom Docker Profiles

```bash
# Start with CPU profile
docker compose --profile cpu up -d

# Start with GPU profile (default)
docker compose up -d
```

### Distributed Ray Deployment

For multi-node Ray clusters, see the main documentation on distributed deployment.

## Support

For issues specific to the Ansible deployment:
1. Check the Ansible logs
2. Verify inventory configuration
3. Test SSH connectivity: `ansible all -i inventory.ini -m ping`
4. Check system requirements

For OpenRAG application issues, refer to the main project documentation.
