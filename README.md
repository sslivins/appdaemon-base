# appdaemon-base

Builds the pinned [AppDaemon](https://appdaemon.readthedocs.io/) container image
used to run my Home Assistant automation apps, plus the `docker-compose.yaml`
that runs it.

> Personal project, shared as-is.

## Why this exists

The deployment previously ran `acockburn/appdaemon:latest` directly. `:latest`
can change underneath you, so this repo pins the version
(`FROM acockburn/appdaemon:4.4.2`) and gives a single place to add system /
Python dependencies and, eventually, the shared `home_lib` library.

## Layout on the server

The apps are **not** baked into this image. Config and apps live in a host
directory bind-mounted at `/conf`, and each app is its own git clone:

```
conf/
  appdaemon.yaml          # runtime config + shared logs: (with secrets - NOT in git)
  apps/
    apps.yaml
    home_lib/             # git clone of appdaemon-home-lib  (shared library)
    device_controller/    # git clone of appdaemon-device-controller
    door_courtesy_lights/ # git clone of appdaemon-door-courtesy-lights
    outdoor_lights_off/   # git clone of appdaemon-outdoor-lights
    doorman/              # git clone of appdaemon-doorman
    hvac_watchdog/        # git clone of appdaemon-hvac-watchdog
    unifi_screen_watchdog/# git clone of appdaemon-unifi-screen-watchdog
```

AppDaemon adds every sub-directory of `apps/` to `sys.path`, so a shared module
in `apps/home_lib/home_lib.py` is importable by bare name (`from home_lib import
...`) from any app. Each app directory can be independently `git pull`ed.

## Run it

```sh
git clone https://github.com/sslivins/appdaemon-base
cd appdaemon-base
docker compose up -d --build
```

## Managing apps with `install_app.py`

Each app is a standalone git clone under `conf/apps/<name>/`, but some apps need
to extend the **shared** top-level `appdaemon.yaml` - most commonly to register a
named log under `logs:`. `install_app.py` (run on the server, from this repo)
does that idempotently and comment-safely, so the shared file never drifts and
you never hand-edit it.

> The server has **no git credentials**, so every app repo it clones must be
> **public**. All current apps are public.

`--conf` defaults to `../appdaemon/conf` relative to this repo (override with
`--conf PATH` or the `APPDAEMON_CONF` env var). On the server the conf lives at
`~/docker/appdaemon/conf`, so the examples below pass it explicitly.

### Install a new app

Clone the repo into `conf/apps/<name>/`, wire its `install/` fragments into
`appdaemon.yaml`, and restart the container:

```sh
cd ~/docker/appdaemon-base
python3 install_app.py unifi_screen_watchdog \
    --repo https://github.com/sslivins/appdaemon-unifi-screen-watchdog \
    --conf ~/docker/appdaemon/conf \
    --restart
```

`--branch B` selects a branch when cloning. If the directory is already a clone,
`--repo` just `git pull`s it.

### Update an app

Pull the latest code, re-apply its fragments (idempotent - replaces its managed
blocks in place), and restart:

```sh
git -C ~/docker/appdaemon/conf/apps/unifi_screen_watchdog pull
python3 install_app.py unifi_screen_watchdog --conf ~/docker/appdaemon/conf --restart
```

Re-running `install_app.py` without `--repo` is always safe - it only rewrites
the block between this app's markers and leaves everything else untouched.

### Remove an app

Strip its config blocks from `appdaemon.yaml` **and** delete its clone:

```sh
python3 install_app.py unifi_screen_watchdog --conf ~/docker/appdaemon/conf --remove --restart
```

### List what's installed

Every managed block is bracketed by markers, so you can see all wired apps with:

```sh
grep '>>> .*install_app.py' ~/docker/appdaemon/conf/appdaemon.yaml
```

## Authoring an app's `install/` directory

An app opts in by shipping an `install/` directory at its repo root:

- `install/<section>.yaml` - a YAML block merged **under** the top-level
  `appdaemon.yaml` key `<section>:`. The filename selects the section, so
  `install/logs.yaml` extends `logs:` (a future `install/secrets.yaml` would
  extend `secrets:`). Author it **2-space indented**, exactly as it should
  appear beneath that key. If the section doesn't exist it's created at EOF.
- `install/hook.py` - optional; run as `python hook.py <conf> <app_dir>` for
  anything that isn't a YAML merge (pip installs, generating files, etc.).

Each merged block is wrapped in
`# >>> <name>:<section> (install_app.py) >>>` / `# <<< <name>:<section> <<<`
markers, so re-running just replaces what's between them - fully idempotent.
`appdaemon.yaml` is validated (parsed as YAML) and written atomically; nothing
outside the markers is ever touched.

Example `install/logs.yaml` for an app named `unifi_screen_watchdog`:

```yaml
  unifi_screen_watchdog_log:
    name: UnifiScreen
    filename: /conf/apps/unifi_screen_watchdog/unifi_screen_watchdog.log
    log_size: 1048576
    log_generations: 10
    format: "{asctime}.{msecs:03.0f} {levelname:<7} {message}"
    date_format: "%Y-%m-%d %H:%M:%S"
```

Once `home_lib` stabilises, bake it into this image instead of cloning it into
`apps/` - e.g. `RUN pip install "git+https://github.com/sslivins/appdaemon-home-lib"`
in the Dockerfile - and drop it from `global_dependencies`. Until then it stays a
cloneable sub-directory so it keeps AppDaemon's edit-and-hot-reload loop.
