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

## Phase 2 (later)

Once `home_lib` stabilises, bake it into this image instead of cloning it into
`apps/` - e.g. `RUN pip install "git+https://github.com/sslivins/appdaemon-home-lib"`
in the Dockerfile - and drop it from `global_dependencies`. Until then it stays a
cloneable sub-directory so it keeps AppDaemon's edit-and-hot-reload loop.
