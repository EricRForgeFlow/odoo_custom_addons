---
name: doodba-sandboxes
description: How the Doodba sandboxes that run and test the addons of odoo_custom_addons are built and operated (../odoo-sandbox-19, ../odoo-sandbox-20, one per Odoo version, upstream Doodba + ForgeFlow overlay). Use this skill whenever the task involves running, starting, debugging or testing a module of this repo in Odoo, installing or updating a module in a database, adding a new module to a sandbox, mounting code, invoke tasks (git-aggregate, img-build, resetdb, test), docker compose problems, enterprise cloning or SSH errors, switching or adding Odoo versions, git worktrees per version, or copier template updates — even if the user just says "run the tests", "it doesn't show up in Apps" or "set up 18.0" without naming Doodba.
---

# Doodba sandboxes for odoo_custom_addons

The addons in this repository are developed and tested in Doodba projects that live next to
it, one per Odoo version. Each sandbox bind-mounts individual modules from this repo (or from
a per-version git worktree of it) into its Odoo container. The README of this repo is the
human-facing version of this document. Keep the two consistent when the setup changes.

```
Repositoris/
├── odoo_custom_addons/          this repo (20.0 code); the 20.0 sandbox mounts from here
├── odoo_custom_addons-19/       git worktree on a 19.0 branch (create when needed)
├── odoo-sandbox-20/             Doodba, Odoo 20.0 → http://localhost:20069
├── odoo-sandbox-19/             Doodba, Odoo 19.0 → http://localhost:19069
└── forgeflow-doodba-template/   local clone of the overlay, with 20.0 added (uncommitted)
```

## Start by looking at the current state

Run the status script before changing anything. It shows each sandbox's Odoo and template
versions, whether OCB and enterprise have been cloned, which services are running, and every
mounted module, including the branch it's served from and any problem with it:

```bash
.claude/skills/doodba-sandboxes/scripts/sandbox_status.sh            # all ../odoo-sandbox-*
.claude/skills/doodba-sandboxes/scripts/sandbox_status.sh ../odoo-sandbox-19
```

It reads the merged `docker compose config`, so it reports what Docker will actually mount.
Most "module not found" problems show up right away as `PROBLEM:` lines.

## How a sandbox is put together

Two copier templates are layered:

1. Upstream `gh:Tecnativa/doodba-copier-template` (v10.0.5), answers in `.copier-answers.yml`.
   It provides `devel.yaml` (symlinked as `docker-compose.yml`), `tasks.py` (invoke) and
   `odoo/custom/`.
2. The ForgeFlow overlay `forgeflow-doodba-template`, answers in `.copier-answers.ff.yml`. It
   adds `scripts/` (restore, worktree runtimes, custom scripts), `inverseproxy.yaml`,
   monitoring, GitLab CI, and its own files under `odoo/custom/src/private/scripts/`.

Three local files sit on top. Put local changes in these, not in template-managed files,
because `copier update` rewrites template files:

- `odoo/custom/src/repos.yaml`: git-aggregator configuration. OCB (`./odoo`, remote `ocb`) and
  `git@github.com:ForgeFlow/enterprise.git` (`./enterprise`), both at `$ODOO_VERSION`, so the
  same file works in every sandbox.
- `odoo/custom/src/addons.yaml`: `enterprise: ["*"]`. This makes enterprise addons available
  but doesn't install them. Addons in `src/private/` are always available and need no entry.
- `docker-compose.override.yml`: Compose loads it automatically on top of `devel.yaml`, and
  every invoke task uses plain `docker compose`. It does two things:
  - **Mounts modules into `services.odoo.volumes`**, one per module:
    `../odoo_custom_addons/<mod>:/opt/odoo/custom/src/private/<mod>:rw,z`. The whole repo
    can't be mounted over `src/private/` because that would hide the overlay's scripts.
  - **Forwards the host SSH agent into `services.devel-setup`.** `invoke git-aggregate` runs
    git inside that container as UID 1000 with `HOME=/home/odoo`, and that user can't read
    the image's root-only `~/.ssh`. Cloning private `ForgeFlow/enterprise` would fail without
    the forwarding. The override mounts `$SSH_AUTH_SOCK` and the project's
    `odoo/custom/ssh/known_hosts` and sets `GIT_SSH_COMMAND` with strict host-key checking.
    `${SSH_AUTH_SOCK:?}` makes every compose command fail fast if no agent is running.

Ports are `<version>` followed by the usual suffix: Odoo `…069`, longpolling `…072`, mail
catcher `…025`, wdb `…984`, pgweb `…081`, debugpy `…899`. That's why sandboxes for different
versions can run side by side. The devel database is `devel`, and the login is admin / admin.

## Common tasks

Run invoke from inside the sandbox folder.

**Run and inspect**

```bash
invoke start | stop | restart | logs
invoke install --modules=a,b                       # installs only; skips installed modules
docker compose run --rm odoo odoo -u a --stop-after-init   # update an installed module
invoke test --modules=a                            # tests, including tours/HttpCase
invoke test --modules=a --mode=init                # tests on a fresh install
invoke resetdb --modules=a                         # DESTROYS and recreates the devel DB
```

`invoke install` runs `addons init`, which installs modules but doesn't update ones that are
already installed. After changing data files or model fields, use the `-u` command above and
then `invoke restart`. Odoo runs with `--dev=reload,qweb,werkzeug,xml,access`, so plain Python
and view edits are usually picked up live.

**Add a module to a sandbox**

1. The module must exist in the mount source on the branch checked out there (a
   `__manifest__.py` with the right version prefix).
2. Add the mount under `services.odoo.volumes` in the sandbox's `docker-compose.override.yml`.
   In `odoo-sandbox-19`, replace the `[]` placeholder with a list.
3. `mkdir odoo/custom/src/private/<mod>` in the sandbox. The parent mount is read-only, so
   Docker can't create the mount point and the container fails to start without it.
4. `invoke stop && invoke start` (the container must be recreated for new mounts), then
   `invoke install --modules=<mod>`.
5. Rerun `sandbox_status.sh`. The module should show `OK`.

**First start of a fresh sandbox**: `invoke git-aggregate` (clones at depth 100, slow),
`invoke img-build --pull`, `invoke resetdb [--modules=…]`, `invoke start`.

**Work on another Odoo version**: give that version its own worktree instead of switching
branches in this checkout, so each sandbox always mounts code for its own version:
`git worktree add ../odoo_custom_addons-19 19.0` (or a feature branch based on 19.0), then
mount from `../odoo_custom_addons-19/<mod>` in `odoo-sandbox-19`. Branch names follow the OCA
convention: version branches `19.0`/`20.0`, feature branches `<version>-<add|imp|fix|mig>-<module>`
started from them (e.g. `20.0-add-tour_manager`). See the README's *Branches* section.

**Create a sandbox for a new version** (XX):

```bash
copier copy --trust -d odoo_version=XX.0 -d project_name=sandbox-XX \
    gh:Tecnativa/doodba-copier-template ../odoo-sandbox-XX
cd ../odoo-sandbox-XX
copier copy --trust --overwrite git@gitlab.forgeflow.io:forgeflow/forgeflow-doodba-template.git .
cp ../odoo-sandbox-20/odoo/custom/src/{repos,addons}.yaml odoo/custom/src/
cp ../odoo-sandbox-19/docker-compose.override.yml .
```

Answers used so far: Traefik 3, `odoo_listdb: no`, Postgres 18 with `backup_db_version: 18`,
empty `backup_dst`, a placeholder `test_ssh_host`. Add `--defaults -d key=value …` to run
without prompts. `--overwrite` is needed because the overlay replaces
`odoo/custom/ssh/known_hosts` (upstream's entries plus `gitlab.forgeflow.io`). Without it,
copier stops halfway in a non-interactive shell.

**Update templates**: upstream first (`copier update --trust`), then the overlay
(`copier update --trust -a .copier-answers.ff.yml`). Review with `git status` / `git diff`.
The sandboxes are git repos with no commits, so the diff shows exactly what changed.

## Things that will bite

- **A mount serves whatever branch is checked out.** If `odoo_custom_addons` is on `master`
  and the module only exists on a feature branch, the folder holds at most stale
  `__pycache__` and Odoo can't find the module. Check the branch before debugging Odoo itself.
- **20.0 and the overlay.** The official overlay (v2.20.0) only accepts versions up to 19.0.
  `odoo-sandbox-20` was generated from `../forgeflow-doodba-template`, where `20.0` was added
  to `odoo_version.choices` in `copier.yaml` (uncommitted). It needs `--vcs-ref HEAD`;
  otherwise copier takes the latest tag and drops the edit. Its `.copier-answers.ff.yml`
  therefore records a temporary commit (`v2.20.0-1-g…`) that no remote has, so a plain
  `copier update -a .copier-answers.ff.yml` fails there. Once an overlay release supports
  20.0, point `_src_path` back to the GitLab URL and update with `--vcs-ref <tag>`.
  `odoo-sandbox-19` uses the official release and updates normally.
- **`could not read Username for 'https://github.com'`** during aggregation is GitHub's
  anonymous rate limit, not missing access. Export a read-only PAT as `DOODBA_GITHUB_TOKEN`
  (`docs/github-auth.md` in the sandbox).
- **`Permission denied (publickey)` for enterprise**: the agent has no key with access to
  `ForgeFlow/enterprise`. Check with `ssh-add -l` and
  `git ls-remote git@github.com:ForgeFlow/enterprise.git`.
- **`python3` on the host** may still resolve to the old `../odoo/.venv`. Don't rely on
  third-party Python packages from the host; work inside the container
  (`docker compose run --rm odoo …`) instead.
- **Leftovers from the old setup** in this repo still assume odoo-bin: `ruff.toml` extends
  `../odoo/ruff.toml`, `.vscode/launch.json` runs odoo-bin, and `odoo.conf.example` remains.
  With Doodba, the core source is at `../odoo-sandbox-<v>/odoo/custom/src/odoo`.

## Ask before running these

- `invoke resetdb`, `invoke stop --purge`, `docker compose down -v`: they destroy databases
  and filestores.
- `copier update` / `copier copy --overwrite` on an existing sandbox: they rewrite files.
- Committing or pushing in any of these repositories: the user decides when that happens.
