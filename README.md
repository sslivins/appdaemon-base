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
  appdaemon.yaml          # runtime config (with secrets - NOT in git)
  apps/
    apps.yaml
    home_lib/             # git clone of appdaemon-home-lib  (shared library)
    device_controller/    # git clone of appdaemon-device-controller
    door_courtesy_lights/ # git clone of appdaemon-door-courtesy-lights
    outdoor_lights_off/   # git clone of appdaemon-outdoor-lights
    doorman/              # git clone of appdaemon-doorman
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

## Installing an app (`install_app.py`)

Apps are self-contained, but some need to extend the **shared** top-level
`appdaemon.yaml` - most commonly to register a named log under `logs:`.
`install_app.py` applies those extensions idempotently and comment-safely so the
shared file never drifts and apps don't have to hand-edit it.

An app opts in by shipping an `install/` directory at its repo root:

- `install/<section>.yaml` - a YAML block merged **under** the top-level
  `appdaemon.yaml` key `<section>:`. The filename selects the section, so
  `install/logs.yaml` extends `logs:`. Author it 2-space indented (exactly as it
  should appear beneath that key). If the section doesn't exist it is created.
- `install/hook.py` - optional; run as `python hook.py <conf> <app_dir>` for
  anything that isn't a YAML merge (pip installs, generating files, etc.).

Each merged block is wrapped in
`# >>> <name>:<section> (install_app.py) >>>` / `# <<< <name>:<section> <<<`
markers, so re-running just replaces what's between them - fully idempotent.
`appdaemon.yaml` is validated and written atomically.

```sh
# clone/pull the app, wire its install/ fragments, restart the container
python install_app.py unifi_screen_watchdog \
    --repo https://github.com/sslivins/appdaemon-unifi-screen-watchdog \
    --restart

# re-apply after editing an install/ fragment (idempotent)
python install_app.py unifi_screen_watchdog

# uninstall: remove its config blocks + the app clone
python install_app.py unifi_screen_watchdog --remove
```

`--conf` defaults to `../appdaemon/conf` relative to this repo (override with
`--conf PATH` or `APPDAEMON_CONF`). `--branch` selects a branch when cloning.

## Phase 2 (later)

Once `home_lib` stabilises, bake it into this image instead of cloning it into
`apps/` - e.g. `RUN pip install "git+https://github.com/sslivins/appdaemon-home-lib"`
in the Dockerfile - and drop it from `global_dependencies`. Until then it stays a
cloneable sub-directory so it keeps AppDaemon's edit-and-hot-reload loop.
