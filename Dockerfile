# Base AppDaemon image for the home automation apps.
#
# Pins the AppDaemon version (the deployment previously ran
# `acockburn/appdaemon:latest`, which can change underneath you). Build and run
# this image instead so the runtime is reproducible.
#
# This is intentionally a thin wrapper today. It's the place to add:
#   * extra system / Python dependencies the apps need, and
#   * (phase 2) the shared `home_lib` library, baked in once it has stabilised,
#     e.g.  RUN pip install "git+https://github.com/sslivins/appdaemon-home-lib"
#     so it no longer has to live loose in the apps directory.
FROM acockburn/appdaemon:4.4.2

# Example for future shared deps (kept commented until needed):
# RUN pip install --no-cache-dir <package>
