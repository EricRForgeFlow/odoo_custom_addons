# odoo_custom_addons

Custom Odoo 20.0 addons. Expects these sibling checkouts:

```
../odoo         # Odoo community (20.0), with its virtualenv at ../odoo/.venv
../enterprise   # Odoo enterprise (20.0)
```

## Setup

```bash
cp odoo.conf.example odoo.conf   # then set the absolute paths for your machine
```

`odoo.conf` is git-ignored. It uses the local PostgreSQL socket as your OS user.
The filestore lives in `.filestore/`, which is also ignored.

Note: Odoo skips an addons path that has no modules in it, so this repo is only
added to the path once it has at least one module.

## Running

```bash
../odoo/.venv/bin/python ../odoo/odoo-bin -c odoo.conf -d <db> --dev=xml,reload
# install / update modules
../odoo/.venv/bin/python ../odoo/odoo-bin -c odoo.conf -d <db> -u my_module
# run a module's tests
../odoo/.venv/bin/python ../odoo/odoo-bin -c odoo.conf -d <test_db> -i my_module \
    --test-tags /my_module --stop-after-init --http-port 8079
```

VS Code launch configs for run, update and test are in `.vscode/launch.json`.

## Code style

`ruff.toml` extends Odoo's own `../odoo/ruff.toml`: `ruff check .` / `ruff format .`.
