# mcwaiter

Minecraft server configurator and controller for Linux.

> ⚠️ **Status:** Early beta. Expect breaking changes.
> Please open issues or start a discussion if you find
> any bugs or would like to request a feature.

Create Minecraft servers and run each one as a sandboxed systemd service
under its own system user (`mcwaiter-<name>`).

## Features

- Create servers for many loaders (Vanilla, Fabric, Paper, ...) with one command,
  using the [MCJars](https://mcjars.app) API
- Interactive prompts for anything you don't pass as an argument
- Finds a matching Java installation automatically (based on the Minecraft version)
- Generates a ready-to-use `run.sh` and a commented `user_jvm_args.txt` (Aikar flags)
- Service hardening and resource limits, configurable globally and per server
- Live console: follows the server log and sends commands via RCON
- Optional autostart of all servers on boot

## Requirements

- Linux with systemd (other service managers are not supported yet)
- Python 3.10+
- Root privileges for most commands (mcwaiter re-runs itself with `sudo` when needed)
- Java (mcwaiter looks for installed JDKs in `/usr/lib/jvm`)

## Installation
```bash
pipx install mcwaiter
```
or directly via git
```bash
pipx install git+https://github.com/Aintdev/mcwaiter.git
```

## Quick start

```bash
# create a server (asks for anything you leave out)
mcwaiter create survival --version 1.20.1 --loader fabric

mcwaiter start survival
mcwaiter console survival
mcwaiter stop survival
```

## Commands

```
mcwaiter [--version] <command> [options]
```

| Command                  | Description                                              | Needs root |
|--------------------------|----------------------------------------------------------|:----------:|
| `create <name>`          | Create a server                                          | yes        |
| `delete <name>`          | Delete a server and its user                             | yes        |
| `start <name>`           | Start a server                                           | yes        |
| `stop <name>`            | Stop a server                                            | yes        |
| `restart <name>`         | Restart a server                                         | yes        |
| `status <name>`          | Show the systemd status of a server                      | no         |
| `console <name>`         | Open the live console                                    | yes        |
| `shell <name>`           | Open a shell as the server's user                        | yes        |
| `edit <name> <relpath>`  | Edit a file in the server directory                      | yes        |
| `chown <name>`           | Fix ownership of all server files                        | yes        |
| `ls`                     | List all servers and whether they are running            | no         |
| `config`                 | Edit the global config (or a server's config with `-n`)  | with `-n`  |
| `autostart`              | Manage and run autostart                                 | yes        |

Every command accepts `--debug`. In debug mode, API responses are saved to
`<config dir>/.debug/api`.

### create

```bash
mcwaiter create <name> [--version MC_VERSION] [--loader LOADER[@BUILD]]
```

`--loader` takes the format `loader@build`, for example `fabric@0.20.1`. If you
leave out the build (just `fabric`), mcwaiter lists the available ones and lets
you choose; the latest stable build is marked `[STBL]`. Missing arguments are
asked interactively.

mcwaiter picks a matching Java version (or asks), writes `run.sh` and
`user_jvm_args.txt` (6 GB heap by default) and asks you to accept the
[Minecraft EULA](https://aka.ms/MinecraftEULA). If anything fails, the
half-created server is cleaned up again.

### delete

```bash
mcwaiter delete <name>
```

You have to type a random confirmation string. For scripts you can skip that
with `--confirm-override` (use at your own risk, this cannot be undone).

### edit / config

```bash
mcwaiter edit survival server.properties   # file path is relative to the server root
mcwaiter config                            # global config
mcwaiter config -n survival                # per-server config
mcwaiter config -e nano                    # set the editor and use it
mcwaiter config -n survival -e nano        # per-server config with nano as editor
```

The editor is stored in the config (`[DEFAULTS] editor`) and asked for on first use.
`edit` fixes file ownership afterwards.

### console

Follows the server log (via `journalctl`) in a curses interface. If RCON is
enabled in the server's `server.properties`, you can type commands at the
bottom (up/down for history, PageUp/PageDown to scroll). Without RCON the log is
read-only.

#### Enabling RCON

Open `server.properties` with `mcwaiter edit <name> server.properties` and set
a port and a password of your choice:

```ini
enable-rcon=true
rcon.port=25575
rcon.password=your-safe-password
```

### autostart

```bash
mcwaiter autostart --enable    # install a systemd unit that starts your servers on boot
mcwaiter autostart --disable   # remove it again
mcwaiter autostart --run       # start all servers with autostart enabled (what the unit runs)
```

A server takes part in autostart when `autostart = true` is set in its
`[OVERRIDES]` section (`mcwaiter config -n <name>`). Servers are started in
alphabetical order.

## How it works

- Servers are in `/opt/mcservers/<name>` (configurable via `serverpath`).
- Each server runs as the system user `mcwaiter-<name>`.
- `start` launches `run.sh` as a transient systemd unit named
  `minecraft-<name>` (via `systemd-run`), so you can also use `systemctl` and
  `journalctl` on it directly.
- Per-server settings are stored next to the server directory in
  `/opt/mcservers/<name>.ini`.

## Configuration

The global config is a `config.ini` in your user config directory
(`~/.config/mcwaiter/` on most systems).

### `[DEFAULTS]`

| Option            | Default            | Description                          |
|-------------------|--------------------|--------------------------------------|
| `serverpath`      | `/opt/mcservers/`  | Where servers are stored             |
| `editor`          | *(empty)*          | Editor used by `edit` and `config`   |
| `shell`           | path of `bash`     | Shell used by `shell` and `run.sh`   |
| `service-manager` | `systemd`          | Detected automatically               |

### `[JAVA]`

`auto` points to the default `java` binary and in the selection panel while creating a server, is listed under `symlink`. 
Detected JDKs are added automatically as `<jdk-name> = <path>` 
(for example `java-21-openjdk = /usr/lib/jvm/java-21-openjdk/bin/java`).

### `[SERVICE]`

These are the defaults for all servers. Each server can override any of them in
its own `[OVERRIDES]` section; an empty value falls back to the global one.
A config file is owned by root and the minecraft-user cannot access it.

| Option              | Default      | Effect                                                                        |
|---------------------|--------------|-------------------------------------------------------------------------------|
| `harden`            | `true`       | `NoNewPrivileges`, `RestrictSUIDSGID`, `LockPersonality`, `RestrictRealtime`  |
| `network-isolation` | `false`      | `PrivateNetwork` (no network access at all)                                   |
| `deny-network`      | `false`      | `IPAddressDeny=any` (ignored if `network-isolation` is on)                    |
| `private-tmp`       | `true`       | `PrivateTmp`                                                                  |
| `private-devices`   | `true`       | `PrivateDevices`                                                              |
| `protect-kernel`    | `true`       | Protects kernel tunables, modules, logs and control groups                    |
| `read-only-system`  | `false`      | `ProtectSystem=strict`, `ProtectHome=yes`                                     |
| `auto-restart`      | `on-failure` | systemd `Restart=` policy (`no` disables it)                                  |
| `restart-sec`       | `5s`         | systemd `RestartSec=` (`0` disables it)                                       |
| `memory-limit`      | `0`          | `MemoryMax=` (`0` = unlimited)                                                |
| `cpu-quota`         | `0`          | `CPUQuota=` (`0` = unlimited)                                                 |
| `tasks-limit`       | `0`          | `TasksMax=` (`0` = unlimited)                                                 |

Boolean options accept the usual `configparser` values (`true`/`false`,
`yes`/`no`, `on`/`off`, `1`/`0`).

Example of a per-server config (`/opt/mcservers/survival.ini`):

```ini
[OVERRIDES]
autostart = true
memory-limit = 8G
private-devices =
```

## Development

```bash
git clone https://github.com/Aintdev/mcwaiter.git
cd mcwaiter
pip install -e .
mcwaiter --help
```

## License

[MIT](https://github.com/Aintdev/mcwaiter/blob/master/LICENSE)