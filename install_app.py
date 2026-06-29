#!/usr/bin/env python3
"""Install (or update) an AppDaemon app into this container's config.

Each app is its own git clone under ``<conf>/apps/<name>/`` (see README). Some
apps need to extend the **shared** top-level ``appdaemon.yaml`` - most commonly
to register a named log under ``logs:``, but potentially other sections too.
This script applies those extensions idempotently and comment-safely, so apps
stay self-contained and the shared file never drifts.

An app opts in by shipping an ``install/`` directory at its repo root:

* ``install/<section>.yaml`` - a block to merge **under** the top-level
  ``appdaemon.yaml`` key ``<section>:`` (authored 2-space indented, i.e. exactly
  as it should appear beneath that key). The filename selects the section, so
  ``install/logs.yaml`` extends ``logs:``; a future ``install/secrets.yaml``
  would extend ``secrets:``. If the section doesn't exist yet it is created.
* ``install/hook.py`` - optional; run as ``python hook.py <conf> <app_dir>``
  for anything that isn't a YAML merge (pip installs, file generation, etc.).

Each merged block is wrapped in
``# >>> <name>:<section> (install_app.py) >>>`` / ``# <<< <name>:<section> <<<``
markers; re-running replaces what's between them, so the operation is fully
idempotent. ``appdaemon.yaml`` is validated and written atomically; nothing
outside the markers is ever touched.

Usage::

    install_app.py <name> [--repo URL] [--branch B] [--conf PATH]
                          [--restart] [--remove]
"""

import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile

import yaml


def _default_conf():
    """conf lives at <repo>/../appdaemon/conf on the server; allow override."""
    env = os.environ.get("APPDAEMON_CONF")
    if env:
        return os.path.abspath(env)
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(here, "..", "appdaemon", "conf"))


def _markers(name, section):
    return (f"  # >>> {name}:{section} (install_app.py) >>>",
            f"  # <<< {name}:{section} <<<")


def _strip_section(lines, name, section):
    """Remove an existing managed block for *name*/*section* (one section)."""
    begin, end = _markers(name, section)
    out, skip = [], False
    for ln in lines:
        if ln.rstrip("\n") == begin:
            skip = True
            continue
        if skip and ln.rstrip("\n") == end:
            skip = False
            continue
        if not skip:
            out.append(ln)
    return out


def _strip_all(lines, name):
    """Remove every managed block for *name* across all sections."""
    prefix = f"  # >>> {name}:"
    out, skip = [], False
    for ln in lines:
        if ln.startswith(prefix) and ln.rstrip("\n").endswith(">>>"):
            skip = True
            continue
        if skip and ln.lstrip().startswith(f"# <<< {name}:"):
            skip = False
            continue
        if not skip:
            out.append(ln)
    return out


def _section_insert_index(lines, section):
    """Index to insert under top-level ``<section>:``; create it if absent.

    Returns ``(lines, index)`` - lines may be mutated to add the section header.
    """
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith(f"{section}:"):
            start = i
            break
    if start is None:
        # Section doesn't exist - create it at EOF.
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{section}:\n")
        return lines, len(lines)
    for j in range(start + 1, len(lines)):
        s = lines[j]
        if s.strip() and not s.startswith((" ", "\t", "#")):
            return lines, j
    return lines, len(lines)


def _inject(conf_yaml, name, section, snippet):
    with open(conf_yaml, "r", encoding="utf-8") as f:
        lines = f.readlines()
    lines = _strip_section(lines, name, section)

    begin, end = _markers(name, section)
    snip = snippet.rstrip("\n").splitlines()
    block = [begin + "\n"] + [s + "\n" for s in snip] + [end + "\n"]
    lines, idx = _section_insert_index(lines, section)
    if idx > 0 and not lines[idx - 1].endswith("\n"):
        lines[idx - 1] += "\n"  # guard the missing-newline bug
    lines[idx:idx] = block

    _write(conf_yaml, "".join(lines))


def _remove_all(conf_yaml, name):
    with open(conf_yaml, "r", encoding="utf-8") as f:
        lines = f.readlines()
    _write(conf_yaml, "".join(_strip_all(lines, name)))


def _write(conf_yaml, new):
    yaml.safe_load(new)  # validate before writing
    d = os.path.dirname(conf_yaml)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(new)
    os.replace(tmp, conf_yaml)


def _git(app_dir, repo, branch):
    if os.path.isdir(os.path.join(app_dir, ".git")):
        print(f"pulling {app_dir}")
        subprocess.run(["git", "-C", app_dir, "pull", "--ff-only"], check=True)
    else:
        print(f"cloning {repo} -> {app_dir}")
        cmd = ["git", "clone"]
        if branch:
            cmd += ["--branch", branch]
        cmd += [repo, app_dir]
        subprocess.run(cmd, check=True)


def _apply_install_dir(conf_yaml, conf, name, app_dir):
    install_dir = os.path.join(app_dir, "install")
    if not os.path.isdir(install_dir):
        print(f"no install/ dir in {app_dir}; nothing to wire")
        return
    for path in sorted(glob.glob(os.path.join(install_dir, "*.yaml"))):
        section = os.path.splitext(os.path.basename(path))[0]
        with open(path, encoding="utf-8") as f:
            _inject(conf_yaml, name, section, f.read())
        print(f"merged install/{section}.yaml under '{section}:'")
    hook = os.path.join(install_dir, "hook.py")
    if os.path.isfile(hook):
        print("running install/hook.py")
        subprocess.run([sys.executable, hook, conf, app_dir], check=True)


def main():
    ap = argparse.ArgumentParser(description="Install an AppDaemon app into appdaemon.yaml.")
    ap.add_argument("name", help="app directory name under conf/apps/")
    ap.add_argument("--repo", help="git URL to clone/pull first")
    ap.add_argument("--branch", help="branch to clone")
    ap.add_argument("--conf", default=_default_conf(), help="path to conf/ dir")
    ap.add_argument("--restart", action="store_true", help="docker restart appdaemon")
    ap.add_argument("--remove", action="store_true", help="uninstall instead of install")
    args = ap.parse_args()

    conf = os.path.abspath(args.conf)
    conf_yaml = os.path.join(conf, "appdaemon.yaml")
    app_dir = os.path.join(conf, "apps", args.name)
    if not os.path.isfile(conf_yaml):
        raise SystemExit(f"not found: {conf_yaml} (use --conf or APPDAEMON_CONF)")

    if args.remove:
        _remove_all(conf_yaml, args.name)
        if os.path.isdir(app_dir):
            shutil.rmtree(app_dir)
        print(f"removed all config blocks + {app_dir}")
    else:
        if args.repo:
            _git(app_dir, args.repo, args.branch)
        _apply_install_dir(conf_yaml, conf, args.name, app_dir)

    if args.restart:
        print("restarting appdaemon container")
        subprocess.run(["docker", "restart", "appdaemon"], check=True)


if __name__ == "__main__":
    main()
