# Agent Zero Launcher

Agent Zero Launcher is the desktop app for installing, running, switching, and
opening Dockerized Agent Zero Instances without starting from Docker commands.

Use it when you are setting up a new machine, when you want a quiet inventory of
installed Agent Zero images, or when you want one place to open local and remote
Instances.

## Start Fresh On A New Machine

1. Download Agent Zero Launcher from the
   [A0 Launcher releases](https://github.com/agent0ai/a0-launcher/releases).
2. Open the app.
3. If the launcher cannot reach Docker yet, follow the setup dialog.
4. If Agent Zero is already hosted on another computer or VPS, click
   **Add remote Instance** instead of setting up local Docker.

![Launcher runtime setup dialog](../res/usage/launcher/launcher-runtime-setup.png)

The first setup dialog keeps the choice simple:

- **Continue** starts the local runtime setup or refreshes the runtime state.
- **Refresh** checks again after you start Docker yourself.
- **Add remote Instance** saves an existing Agent Zero URL and lets you use the
  Launcher without local Docker.

## Installs

When Docker is ready, Launcher opens to **Installs**. This page shows official
Agent Zero release lines and local images.

![Launcher Installs view](../res/usage/launcher/launcher-installs.png)

Cards usually mean:

- **latest** tracks the newest published Agent Zero release image.
- **ready** tracks the development-ready image when you intentionally work from
  that branch.
- Version cards such as **1.20**, **1.19**, or **1.18** are pinned release
  images.
- **Install** downloads an image.
- **Run** starts an installed image as a local Instance.

## Instances

Open **Instances** after you run Agent Zero. This is where local containers and
saved remote Instances live.

Use the Instance card to:

- open the Web UI;
- start, stop, rename, or delete the container;
- open logs;
- use **Backup `/a0/usr`** to download the same user-data backup you can create
  from Agent Zero Core;
- use **Restore `/a0/usr`** to restore that backup zip into the selected
  Instance;
- open A0 CLI when the host connector is installed.

Launcher keeps local Instances and remote Instances separate, so deleting a
container is not the same as deleting a saved remote URL or a workspace backup.

## Workspace Storage

When creating a local Instance, choose where its **`/a0/usr`** data will live.
This directory holds settings, chats, memory, projects, and custom plugins.
Launcher creates the Docker mount; inside Agent Zero the path stays `/a0/usr`
regardless of the host location you choose.

### Choose Storage For A New Instance

Open **Installs -> Run**, expand **Advanced**, and find **Workspace storage**:

| Option | What Launcher does | Example host location |
| --- | --- | --- |
| **Create folder named after Instance** | Creates a separate folder under your configured host folder and bind-mounts its `usr` subfolder at `/a0/usr`. | With the default root and Instance name `research`: `~/agent-zero/research/usr` |
| **Choose custom folder** | Bind-mounts the exact folder entered in **Folder** at `/a0/usr`, creating it if needed. It does not append `usr`. | `/home/user/agent-zero-data` |
| **Named Docker volume** | Uses Docker-managed storage at `/a0/usr`. Enter a **Volume name**, or leave it blank for a generated name. | A Docker volume rather than a browsable host folder |

If an automatically generated folder name already exists, Launcher chooses a
free name with a numeric suffix. Use **Choose custom folder** to select an
existing data folder deliberately. If your old data is in
`/home/user/old-instance/usr`, select that **`usr` folder**, not its parent.

On the first-instance setup screen, **Persistent workspace (recommended)**
creates the separate host folder. That screen also offers **Named Docker
volume** and **No persistent workspace**. The last choice stores data only in
the container: stopping it keeps the data, but deleting or replacing it can
lose the data.

### Set Defaults And Find Your Files

Open **Settings -> Workspace** to set defaults for new local Instances:

- **Host folder** is the parent directory when **Folder mapping** is
  **Separate folder per Instance**.
- **Use this folder directly** maps that exact folder at `/a0/usr` for flows
  that use the saved defaults. The **Run** dialog has its own storage choice;
  choose **Choose custom folder** there to make an exact mapping for that
  Instance.
- **Named Docker volume** uses the configured **Volume prefix** for generated
  names.

Changing defaults does not move existing Instance data. For an Instance with
a host folder, open its menu on **Instances** and choose **Open storage folder**
to see the actual mounted directory.

For example, with `~/agent-zero/research/usr` mounted, a file you place at
`~/agent-zero/research/usr/reports/notes.txt` is available to Agent Zero as
`/a0/usr/reports/notes.txt`. Edits and deletions affect the same file on both
sides. Use a separate workspace for each running Instance; sharing one writable
data folder can mix settings and chats.

When deleting an Instance, **Keep folder** or **Keep volume** removes the
container while preserving its data. **Delete folder** or **Delete volume**
also removes the associated user data. Keep a backup before choosing deletion.
For an Instance without persistent storage, use **Persist a0/usr data** in its
menu and verify the replacement before removing the old container.

The **Host access -> Folder for files and commands** control belongs to the
host connector. It selects where host file operations and commands start;
commands can reach other host folders. **Workspace storage** controls the
Docker mount. For additional work-folder mounts, read
[Use Local Folders With Agent Zero](local-folders.md#share-a-separate-work-folder).
Saved remote Instances keep their storage on the remote machine.

## Updating With Launcher

For same-major Agent Zero updates, the Web UI **Self Update** is still the
normal path.

For a major image jump such as v1.20 -> v2.0, use Launcher or Docker to start a
new v2.0 Instance, then restore a backup from the old Instance. In Launcher, the
flow is: **Instances -> Backup `/a0/usr`** on the old v1.20 Instance, **Installs
-> latest -> Install/Run**, then **Instances -> Restore `/a0/usr`** on the new
v2.0 Instance. This avoids mixing an old root install with a new Docker image.

See [Updating from v1.20 to v2.0](../setup/installation.md#updating-from-v120-to-v20).

## Capture Launcher Screenshots With Playwright

Launcher is an Electron app, so browser-only Playwright commands are not enough.
Use Playwright's Electron bridge and the local Electron binary from the Launcher
repo.

The pattern below installs Playwright into a temporary folder outside the repo,
launches local Launcher content, waits for the `a0app://content/` window, and
saves a screenshot.

```bash
mkdir -p /tmp/a0-launcher-playwright
npm install --prefix /tmp/a0-launcher-playwright playwright
```

```bash
NODE_PATH=/tmp/a0-launcher-playwright/node_modules node <<'JS'
const { _electron: electron } = require("playwright");

const launcher = "/home/eclypso/a0/a0-launcher";
const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

(async () => {
  const app = await electron.launch({
    executablePath: `${launcher}/node_modules/electron/dist/electron`,
    args: [launcher],
    env: {
      ...process.env,
      A0_LAUNCHER_LOCAL_REPO: launcher,
      ELECTRON_DISABLE_SECURITY_WARNINGS: "true",
    },
  });

  const windows = [];
  app.on("window", (page) => windows.push(page));
  windows.push(await app.firstWindow());

  let page = null;
  const deadline = Date.now() + 45000;
  while (Date.now() < deadline && !page) {
    page = windows.find((item) =>
      item && !item.isClosed() && item.url().startsWith("a0app://content/")
    ) || null;
    if (!page) {
      await app.waitForEvent("window", { timeout: 1000 })
        .then((item) => windows.push(item))
        .catch(() => null);
      await sleep(250);
    }
  }

  if (!page) throw new Error("Launcher content window did not open");

  await page.waitForLoadState("networkidle", { timeout: 10000 }).catch(() => null);
  await sleep(3000);
  await page.screenshot({
    path: `${launcher}/output/playwright/launcher-installs.png`,
    fullPage: false,
  });
  await app.close();
})();
JS
```

For docs screenshots that show the first-run runtime gate without changing the
real machine state, open the real Launcher page and render the real runtime-gate
component with a minimal demo state:

```js
await page.evaluate(async () => {
  const { renderRuntimeGate } = await import(
    "a0app://content/components/docker-manager/runtime-gate/runtime-gate.js"
  );

  renderRuntimeGate({
    stateLoaded: true,
    dockerAvailable: false,
    runtime: {
      platform: "linux",
      state: "not_provisioned",
      action: "install",
      canProvision: true,
      setupActionLabel: "Setup Agent Zero",
      detail: "No local container runtime was found.",
    },
    versions: [{ id: "latest", availability: "available" }],
    images: [],
    containers: [],
    remoteInstances: [],
  }, {
    refresh() {},
    provisionRuntime() {},
    openDockerDownload() {},
    addRemoteInstance() {},
  });
});

await page.locator(".dm-runtime-gate").screenshot({
  path: "/home/eclypso/a0/a0-launcher/output/playwright/launcher-runtime-setup.png",
});
```
