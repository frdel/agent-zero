# Use Local Folders With Agent Zero

Use a Docker **bind mount** to make a folder on your computer available inside
Agent Zero. You choose two paths: the folder on the Docker host and the path
where Agent Zero sees it inside the container.

If you use the desktop app, follow
[Workspace Storage in Launcher](launcher.md#workspace-storage). Launcher creates
the Docker mount for you.

## How The Paths Work

For example, mount `/home/user/agent-zero-data` at `/a0/usr`:

| On your computer | Inside Agent Zero |
| --- | --- |
| `/home/user/agent-zero-data` | `/a0/usr` |
| `/home/user/agent-zero-data/settings.json` | `/a0/usr/settings.json` |
| `/home/user/agent-zero-data/reports/summary.txt` | `/a0/usr/reports/summary.txt` |

These paths refer to the **same files**. A bind mount does not upload or copy
the folder. When Agent Zero writes `summary.txt`, you can open that file on your
computer. When you edit it locally, Agent Zero sees the edit. Tell Agent Zero
the container path, for example: “Read the files in `/a0/usr/reports`.”

Stopping and starting the same container keeps its files, even without a mount.
The difference matters when you **delete or replace** the container:

| Storage choice | Where the files live | After deleting only the container |
| --- | --- | --- |
| Bind mount | A folder you choose on the Docker host | The folder remains |
| Named Docker volume | Storage managed by Docker | The named volume remains until you delete it separately |
| No persistent mount | Inside that container | Its files are lost |

The quick-start option `-v a0_usr:/a0/usr` uses a **named volume**. A host path,
such as `-v /home/user/agent-zero-data:/a0/usr`, creates a **bind mount**.

> [!CAUTION]
> Bind mounts are writable by default. Agent Zero can change or delete files in
> the shared folder, and those changes affect your originals. Persistence is
> not a backup; keep separate backups of important data.

## Keep Agent Zero User Data In A Local Folder

Mount your dedicated data folder at **`/a0/usr`** to keep settings, chats,
memory, projects, and custom plugins outside the container. The folder itself
contains `settings.json`, `chats/`, and other user data; you do not need to add
another `usr` folder inside it.

### Docker CLI

Run this on the computer running Docker. Replace the example host path with
your own absolute path:

```bash
mkdir -p /home/user/agent-zero-data
docker run -d --name agent-zero-local \
  -p 127.0.0.1:50080:80 \
  --mount type=bind,source=/home/user/agent-zero-data,target=/a0/usr \
  agent0ai/agent-zero:latest
```

Open `http://localhost:50080`. Choose a different host port or container name if
either is already in use. With `--mount`, the host folder must exist first.

### Docker Desktop

1. Open **Images**, find `agent0ai/agent-zero`, and click **Run**.
2. Expand **Optional settings** and map a host port to container port **80**.
3. Under **Volumes**, set **Host path** to your local data folder, such as
   `/home/user/agent-zero-data`.
4. Set **Container path** to **`/a0/usr`**, then click **Run**.

Docker Desktop calls this area “Volumes”; entering a host folder path creates
a bind mount. If Docker Desktop asks to share the folder, allow access to that
folder.

### Docker Compose

Save this as `compose.yaml`. Create an `agent-zero-data` folder beside it, then
run `docker compose up -d` from that directory:

```yaml
services:
  agent-zero:
    image: agent0ai/agent-zero:latest
    ports:
      - "127.0.0.1:50080:80"
    volumes:
      - type: bind
        source: ./agent-zero-data
        target: /a0/usr
```

Compose resolves `./agent-zero-data` relative to the Compose file's directory.

> [!CAUTION]
> Use `/a0/usr` for ordinary data persistence. Mounting the whole `/a0` folder
> also keeps application code from the host and can interfere with image
> upgrades. For a major version upgrade, follow the
> [backup and restore instructions](../setup/installation.md#updating-from-v120-to-v20).

## Share A Separate Work Folder

To let Agent Zero work on an existing folder without making it the entire user
data directory, add a second mount. This example keeps Agent Zero data in a
named volume and shares `/home/user/reports` as `/mnt/reports`:

```bash
docker run -d --name agent-zero-reports \
  -p 127.0.0.1:50081:80 \
  --mount type=volume,source=a0_reports_usr,target=/a0/usr \
  --mount type=bind,source=/home/user/reports,target=/mnt/reports \
  agent0ai/agent-zero:latest
```

Create `/home/user/reports` first, then ask Agent Zero to work in
**`/mnt/reports`**. Add `,readonly` to that bind mount if Agent Zero only needs
to read the files. Save generated results under `/a0/usr` or another writable
folder in that case.

The Launcher **Workspace storage** selector configures `/a0/usr`. For an
additional mount at a different container path, use Docker CLI or Compose.
Files mounted at `/mnt/reports` are outside `/a0/usr`; back them up separately
from the Launcher's **Backup `/a0/usr`**.

## Add A Mount To An Existing Instance

Docker sets mounts when it creates the container. Restarting a container does
not add a new mount, and mounting an empty folder does not copy existing user
data into it. The mounted folder hides anything already at the target path.

1. Back up the existing instance using Agent Zero's **Backup & Restore**, or
   **Backup `/a0/usr`** in Launcher.
2. Create a new container with the desired mounts and a different host port.
3. Restore the backup into the new instance and verify chats, settings, and
   projects before deleting the old container.

For a Launcher instance without persistent storage, the Instance menu also
offers **Persist a0/usr data**. It copies the data into persistent storage and
retains the old container until the replacement starts. Verify the replacement
before removing the old one.

## Check The Mapping

Inspect a container's actual mounts with:

```bash
docker inspect agent-zero-local --format '{{range .Mounts}}{{println .Type .Source "->" .Destination "writable:" .RW}}{{end}}'
```

For the CLI example above, look for a `bind` entry from your data folder to
`/a0/usr`. Put a harmless text file in the host folder and ask Agent Zero to
read it through its container path to confirm access.

| Problem | What to check |
| --- | --- |
| Agent Zero cannot find a local file | Use the container path in your prompt and confirm the mount with `docker inspect`. A host path is not automatically available in the container. |
| Settings or chats seem to have disappeared | Check that you mounted the intended data folder. A new or empty folder starts with separate data; restore a backup if needed. |
| Permission denied | Check that Docker can access the host folder and that the mount permits writes. On Linux, also check file ownership and permissions. |
| The instance runs on a VPS or remote Docker host | Bind paths belong to that host. Choosing a folder on your laptop does not mount it into a remote server. |

For host file access through a connected terminal rather than a Docker mount,
see the [A0 CLI Connector](a0-cli-connector.md).
