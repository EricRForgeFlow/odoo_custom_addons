# odoo_custom_addons

Custom Odoo addons. Development and testing run in [Doodba](https://github.com/Tecnativa/doodba)
sandboxes, one per Odoo version. Each sandbox is a sibling folder that bind-mounts modules
from this repository into its Odoo container.

```
Repositoris/
├── odoo_custom_addons/       ← this repo
├── odoo-sandbox-20/          ← Doodba project, Odoo 20.0  → http://localhost:20069
├── odoo-sandbox-19/          ← Doodba project, Odoo 19.0  → http://localhost:19069
└── forgeflow-doodba-template/  ← local clone of the ForgeFlow overlay (needed for 20.0)
```

The sandboxes are local folders and are not pushed anywhere. Each one has its own image,
database volume and copies of Odoo (OCB) and enterprise, so versions never mix, and both can
run at the same time because every port starts with the version number.

## How a sandbox is built

Each sandbox combines two copier templates:

1. **Upstream Doodba** ([doodba-copier-template](https://github.com/Tecnativa/doodba-copier-template)),
   answers in `.copier-answers.yml`.
2. **ForgeFlow overlay** (`forgeflow-doodba-template`), answers in `.copier-answers.ff.yml`.
   It adds `scripts/` (restore, worktrees, custom scripts), `inverseproxy.yaml`, monitoring and
   GitLab CI.

On top of the templates, three files are local:

| File | Purpose |
|---|---|
| `odoo/custom/src/repos.yaml` | Repositories cloned into `odoo/custom/src/`: OCB (`./odoo`) and ForgeFlow's enterprise fork (`./enterprise`), both at `$ODOO_VERSION` |
| `odoo/custom/src/addons.yaml` | Makes all enterprise addons available (`enterprise: ["*"]`). This doesn't install them |
| `docker-compose.override.yml` | Mounts our modules into the container and forwards your SSH agent (see below) |

`docker compose` loads `docker-compose.override.yml` automatically on top of `devel.yaml`, so
`invoke` tasks use it too, and `copier update` never touches it.

### Why the SSH agent is forwarded

`invoke git-aggregate` clones the repositories inside the `devel-setup` container, running git
as UID 1000. That user can't read the SSH keys baked into the image, so cloning the private
`ForgeFlow/enterprise` repository would fail. The override mounts your host's `$SSH_AUTH_SOCK`
and the project's `odoo/custom/ssh/known_hosts` into the container, so git uses your own GitHub
key with strict host-key checking. That means an SSH agent holding a key with access to
`ForgeFlow/enterprise` must be running in the shell where you run `docker compose` / `invoke`.

## Daily use

Run these from inside a sandbox folder (`cd ../odoo-sandbox-20`):

```bash
invoke start                                # start Odoo (+ db, mail catcher, wdb)
invoke logs                                 # follow the logs
invoke restart                              # reload Python code
invoke install --modules=tour_manager       # install a module
docker compose run --rm odoo odoo -u tour_manager --stop-after-init   # update an installed module
invoke test --modules=tour_manager          # run a module's tests (tours included)
invoke test --modules=tour_manager --mode=init   # tests on a fresh install
invoke resetdb --modules=tour_manager       # recreate the devel database with these modules
invoke stop                                 # stop the stack (--purge also drops the volumes)
```

| Service | 20.0 | 19.0 |
|---|---|---|
| Odoo (admin / admin) | http://localhost:20069 | http://localhost:19069 |
| Mail catcher | http://localhost:20025 | http://localhost:19025 |
| wdb debugger (`import wdb; wdb.set_trace()`) | http://localhost:20984 | http://localhost:19984 |
| pgweb | http://localhost:20081 | http://localhost:19081 |

Odoo runs with `--dev=reload,qweb,werkzeug,xml,access`, so most Python and XML changes are
picked up without restarting. Data and model changes still need a module update (`-u`, above),
followed by `invoke restart`.

For the IDE, open `doodba.odoo-sandbox-<version>.code-workspace` in the sandbox. It has the
debugger configuration and path mappings for the container.

## Adding a module

Modules are mounted one by one, not the whole repository. The overlay keeps its own files in
`odoo/custom/src/private/scripts/`, and mounting the repository over `src/private/` would hide
them.

1. Create the module in this repository (`my_module/` with its `__manifest__.py`) on a branch
   of the right Odoo version.
2. In the sandbox, add a mount to `docker-compose.override.yml` under `services.odoo.volumes`:
   ```yaml
   - ../odoo_custom_addons/my_module:/opt/odoo/custom/src/private/my_module:rw,z
   ```
   For a 19.0 module, use the 19.0 worktree as the source (`../odoo_custom_addons-19/my_module`).
3. Create the mount point. The parent folder is mounted read-only, so Docker can't create it:
   ```bash
   mkdir odoo/custom/src/private/my_module
   ```
4. Recreate the container and install the module:
   ```bash
   invoke stop && invoke start
   invoke install --modules=my_module
   ```

Doodba always makes everything in `src/private/` available, so the module doesn't need an
`addons.yaml` entry.

To add an extra repository instead (for example an OCA repository), add it to `repos.yaml`,
list the addons you need in `addons.yaml` and run `invoke git-aggregate`.

### The sandbox serves the checked-out branch

A mount points to a folder, not a branch. `odoo-sandbox-20` serves whatever is checked out in
`odoo_custom_addons/` at that moment. If the module doesn't exist on that branch, Odoo can't
find it. For example, `tour_manager` currently lives on the `20.0-add-tour_manager` branch,
not on `master` or `20.0`.

## Branches

Branches follow the [OCA](https://github.com/OCA) convention:

- **Version branches** (`19.0`, `20.0`) hold the code for one Odoo version. Every module on
  them has a manifest version with that prefix (`20.0.1.0.0`).
- **Feature branches** start from a version branch and merge back into it. They're named
  `<version>-<action>-<module>`, where the action is `add` (new module), `imp` (improvement),
  `fix` or `mig` (migration from another version). Examples: `20.0-add-tour_manager`,
  `19.0-mig-tour_manager`.
- `master` holds the repository tooling (this README, `.claude/`), not modules.

## Working on another Odoo version

Don't switch this checkout between version branches. Give each version its own
[git worktree](https://git-scm.com/docs/git-worktree), so each sandbox always mounts code for
its own version:

```bash
# from this repository; check out the version branch, or a feature branch based on it
git worktree add ../odoo_custom_addons-19 19.0
```

Then mount modules from `../odoo_custom_addons-19/` in `odoo-sandbox-19` as described in
[Adding a module](#adding-a-module). `odoo-sandbox-19` doesn't mount any module yet; its
override file has a commented example.

## First start of a sandbox

```bash
cd ../odoo-sandbox-19            # or ../odoo-sandbox-20
invoke git-aggregate             # clone OCB + enterprise into odoo/custom/src (slow the first time)
invoke img-build --pull          # build the Odoo image
invoke resetdb                   # create the devel database (add --modules=... to install some)
invoke start
```

Run `invoke git-aggregate` again whenever you want newer OCB or enterprise code, followed by
`invoke img-build` if dependencies changed.

## Creating a sandbox for a new version

Both existing sandboxes were created like this. Replace `XX` with the version:

```bash
cd ~/Documents/Repositoris

# 1. Upstream Doodba
copier copy --trust -d odoo_version=XX.0 -d project_name=sandbox-XX \
    gh:Tecnativa/doodba-copier-template odoo-sandbox-XX

# 2. ForgeFlow overlay on top. --overwrite lets it replace odoo/custom/ssh/known_hosts,
#    whose overlay version adds gitlab.forgeflow.io to upstream's entries.
cd odoo-sandbox-XX
copier copy --trust --overwrite \
    git@gitlab.forgeflow.io:forgeflow/forgeflow-doodba-template.git .

# 3. Reuse the local configuration of an existing sandbox
cp ../odoo-sandbox-20/odoo/custom/src/{repos,addons}.yaml odoo/custom/src/
cp ../odoo-sandbox-19/docker-compose.override.yml .   # then add the module mounts
```

Answers used: Traefik 3 as the proxy, `odoo_listdb: no`, Postgres 18 (and `backup_db_version: 18`
in the overlay), and an empty backup destination. The staging and CI questions don't matter
locally, so `test_ssh_host` is a placeholder.

### Odoo 20.0 and the ForgeFlow overlay

The official overlay (v2.20.0) only offers versions up to 19.0. `odoo-sandbox-20` was generated
from the local clone `../forgeflow-doodba-template`, where `20.0` was added to the
`odoo_version` choices in `copier.yaml` (uncommitted):

```bash
copier copy --trust --overwrite --vcs-ref HEAD ../forgeflow-doodba-template .
```

`--vcs-ref HEAD` is required. Without it, copier uses the latest tag and ignores the
uncommitted change. Because of that, `.copier-answers.ff.yml` of `odoo-sandbox-20` records a
temporary commit (`v2.20.0-1-g…`) that doesn't exist anywhere. Once a release of the overlay
includes 20.0, set `_src_path` in that file back to the GitLab URL and update with
`--vcs-ref <new tag>`.

## Updating the templates

Upstream first, then the overlay:

```bash
copier update --trust                             # upstream Doodba
copier update --trust -a .copier-answers.ff.yml   # ForgeFlow overlay
```

Run updates on purpose, one sandbox at a time, and check the diff afterwards. The sandbox folders
are git repositories with no commits, so `git status` and `git diff` show what changed.

## Troubleshooting

- **`start an ssh-agent first`**: the override needs `SSH_AUTH_SOCK`. Run commands from a desktop
  terminal, or start an agent (`eval $(ssh-agent) && ssh-add`).
- **`could not read Username for 'https://github.com'` during git-aggregate**: GitHub rate limits
  anonymous clones. Export a read-only token as `DOODBA_GITHUB_TOKEN` (see `docs/github-auth.md`
  in the sandbox).
- **A module doesn't show up**: check that the mount is in `docker-compose.override.yml`, that
  its mount point exists in `odoo/custom/src/private/`, that the container was recreated
  (`invoke stop && invoke start`), and that the module exists on the checked-out branch.
  Then use *Update Apps List* or `invoke install --modules=<name>`.

## Tools

`tools/` holds what isn't an addon, on `master` with the rest of the tooling:

| Folder | Purpose |
|---|---|
| `tools/forgeflow_reveal/` | ForgeFlow's reveal.js template: slide decks built from YAML (see its README) |
| `tools/demos/<module>/` | The narrated demo video of a module: slides, recording flow and demo data (see its README) |

Videos are recorded with [odoo-demo-recorder](https://gitlab.forgeflow.io/forgeflow/odoo-demo-recorder)
and narrated offline with Kokoro (`kokoro-say`). Generated files (decks, images, audio,
videos) aren't committed.

## Code style

`ruff.toml` extends Odoo's own `../odoo/ruff.toml`: `ruff check .` / `ruff format .`.
