# Agent Zero Docker Configuration

## Container Setup Summary

Two separate Agent Zero instances have been configured with automatic restart policies:

### Instance 1 (Original)
- **Container Name:** Agent-Zero
- **Container ID:** a18e308acf4d
- **Port:** 50080
- **Access URL:** http://localhost:50080
- **Codebase:** /Users/mandelsonfleurival/Documents/agent-zero
- **Restart Policy:** unless-stopped

### Instance 2 (Separate)
- **Container Name:** Agent-Zero-2
- **Container ID:** fd3efdf038e7
- **Port:** 50081
- **Access URL:** http://localhost:50081
- **Codebase:** /Users/mandelsonfleurival/Documents/agent-zero-2
- **Restart Policy:** unless-stopped

## Restart Policy: "unless-stopped"

This policy ensures that both containers will:
- ✅ **Automatically start on system reboot**
- ✅ **Restart automatically if they crash or exit unexpectedly**
- ✅ **Stay stopped when manually stopped by user** (using `docker stop`)
- ✅ **Not restart when Docker daemon starts if manually stopped**

## Management Commands

### View status of both containers:
```bash
docker ps -f name=Agent-Zero
```

### Stop both containers (they will stay stopped):
```bash
docker stop Agent-Zero Agent-Zero-2
```

### Start both containers:
```bash
docker start Agent-Zero Agent-Zero-2
```

### View restart policies:
```bash
docker inspect Agent-Zero Agent-Zero-2 --format='{{.Name}}: {{.HostConfig.RestartPolicy.Name}}'
```

## Key Benefits

1. **High Availability:** Both instances will survive system reboots
2. **Fault Tolerance:** Automatic restart on unexpected failures
3. **User Control:** Manual stop commands are respected
4. **Independent Operation:** Each instance maintains separate data and configuration
5. **Resource Isolation:** Each instance uses its own codebase and database

## Recreating Containers (if needed)

If you need to recreate the containers with the same configuration:

```bash
# For Agent-Zero (Instance 1)
cd /Users/mandelsonfleurival/Documents/agent-zero
docker run -d --name Agent-Zero --restart unless-stopped -p 50080:80 -v "$(pwd)":/a0 --env-file .env frdel/agent-zero-run

# For Agent-Zero-2 (Instance 2)
cd /Users/mandelsonfleurival/Documents/agent-zero-2
docker run -d --name Agent-Zero-2 --restart unless-stopped -p 50081:80 -v "$(pwd)":/a0 --env-file .env frdel/agent-zero-run
