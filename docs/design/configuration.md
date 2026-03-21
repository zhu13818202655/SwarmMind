# SwarmMind Configuration Guide

This document describes the current unified configuration system used by SwarmMind.

The runtime entrypoint is:

```python
from swarmmind.config import get_settings

settings = get_settings()
```

The returned object is `SwarmMindConfig` from [swarmmind/config/settings.py](swarmmind/config/settings.py).

## What Exists Today

The configuration system supports:

1. Pydantic settings models
2. Environment variables
3. `.env`
4. YAML config files
5. JSON config files
6. TOML config files
7. Optional secrets directory

The public config package is:

- [swarmmind/config/__init__.py](swarmmind/config/__init__.py)

Implementation is split into:

- [swarmmind/config/schema.py](swarmmind/config/schema.py): config schema models
- [swarmmind/config/settings.py](swarmmind/config/settings.py): `BaseSettings`, source order, cache
- [swarmmind/config/env.py](swarmmind/config/env.py): environment fallback and `${VAR}` expansion helpers

Legacy imports from [swarmmind/models/config.py](swarmmind/models/config.py) still work, but new code should import from `swarmmind.config`.

## Source Order

Current precedence is high to low:

1. Explicit constructor arguments to `SwarmMindConfig(...)`
2. Environment variables with prefix `SWARMMIND_`
3. `.env`
4. `config.json`
5. `configs/default.yaml`
6. `config.yaml`
7. `config.toml`
8. Files in `.secrets/`

This order comes from [swarmmind/config/settings.py](swarmmind/config/settings.py).

Note that both YAML files are loaded with deep merge enabled. That means `config.yaml` can override part of `configs/default.yaml` without replacing the whole nested object.

## Default Files

By default the loader looks for:

1. `.env`
2. `config.json`
3. `configs/default.yaml`
4. `config.yaml`
5. `config.toml`
6. `.secrets/`

The shipped defaults currently live in [configs/default.yaml](configs/default.yaml).

## Environment Variable Naming

Nested fields use double underscore separators because `env_nested_delimiter="__"` is enabled.

Examples:

```bash
export SWARMMIND_LOG_LEVEL=DEBUG
export SWARMMIND_STORAGE_PATH=./data
export SWARMMIND_API__HOST=0.0.0.0
export SWARMMIND_API__PORT=9000
export SWARMMIND_AGENT__MODEL__NAME=gpt-4o
export SWARMMIND_AGENT__MODEL__API_KEY=sk-xxx
export SWARMMIND_SANDBOX__BASE_URL=http://localhost:45698
export SWARMMIND_IDENTITY__DEFAULT_TENANT_ID=team-a
```

## Compatibility Environment Variables

In addition to `SWARMMIND_*`, some fields support legacy compatibility variables through field validators in [swarmmind/config/schema.py](swarmmind/config/schema.py).

Currently supported compatibility variables are:

1. `OPENAI_API_KEY`
2. `OPENAI_BASE_URL`
3. `OPEN_SANDBOX_API_KEY`
4. `OPEN_SANDBOX_BASE_URL`
5. `OPEN_SANDBOX_CREATE_RETRIES`
6. `OPEN_SANDBOX_CREATE_BACKOFF_SECONDS`

These are useful when reusing common shell environment setups.

## `${VAR}` Placeholder Support

YAML and other file-based values can use a single placeholder in the form `${ENV_VAR}`.

Example from [configs/default.yaml](configs/default.yaml):

```yaml
agent:
  model:
    api_key: ${OPENAI_API_KEY}

sandbox:
  api_key: ${OPEN_SANDBOX_API_KEY}
```

This is handled by `resolve_env_value()` in [swarmmind/config/env.py](swarmmind/config/env.py).

Behavior:

1. If the value is exactly `${OPENAI_API_KEY}`, the loader tries to read `OPENAI_API_KEY`
2. If the env var exists, the placeholder is replaced with the env value
3. If the env var does not exist, the value becomes `None`

This logic currently handles exact placeholders only, not string interpolation inside larger text.

## Current Schema

The top-level config object currently contains:

1. `sandbox`
2. `agent`
3. `api`
4. `identity`
5. `rate_limit`
6. `log_level`
7. `storage_path`

Example shape:

```yaml
sandbox:
  provider: opensandbox
  api_key: ${OPEN_SANDBOX_API_KEY}
  base_url: http://localhost:45698
  default_profile: py-basic
  create_retries: 3
  create_backoff: 1.0

agent:
  model:
    provider: openai
    name: gpt-4o
    api_key: ${OPENAI_API_KEY}
    temperature: 0.7
    max_tokens: 4096
  memory:
    short_term_max_blocks: 10
    long_term_enabled: false
    long_term_storage_type: memory
  max_steps: 100
  timeout: 300

api:
  title: SwarmMind API
  description: A general-purpose AI task assistant API
  version: 0.1.0
  host: 127.0.0.1
  port: 8000
  reload: false

identity:
  default_tenant_id: local
  default_principal_id: developer
  default_scopes:
    - tasks:submit
    - tasks:read
    - runs:read
  default_roles:
    - developer
  auth_method: static

rate_limit:
  enabled: false
  per_minute: 60

log_level: INFO
storage_path: ./data
```

## Current Usage Points

The unified settings object is currently used by:

1. [swarmmind/cli.py](swarmmind/cli.py)
2. [swarmmind/api/server.py](swarmmind/api/server.py)
3. [swarmmind/app/container.py](swarmmind/app/container.py)
4. [swarmmind/app/bootstrap.py](swarmmind/app/bootstrap.py)

This means CLI and API/container now read from the same config source instead of building settings independently.

## Safe Logging

Use `settings.safe_summary()` if you need to log config values.

Example:

```python
from swarmmind.config import get_settings

settings = get_settings()
print(settings.safe_summary())
```

The current implementation masks:

1. `sandbox.api_key`
2. `agent.model.api_key`

## Recommended Patterns

Prefer these imports:

```python
from swarmmind.config import get_settings, SwarmMindConfig
```

Prefer passing settings downward at boundaries when practical, for example `create_app(settings)` or `build_container(settings)`.

Use `get_settings()` for process-wide shared configuration when you want the cached singleton behavior.

## Example Local Setup

Minimal `.env` example:

```dotenv
OPENAI_API_KEY=your-openai-key
OPEN_SANDBOX_API_KEY=your-opensandbox-key
```

Optional override in `config.yaml`:

```yaml
api:
  host: 0.0.0.0
  port: 8010

identity:
  default_tenant_id: local-dev
  default_principal_id: alice
```

## Current Limitations

The current config system intentionally stays simple. Notable limitations:

1. No profile selection mechanism like `--config-profile dev`
2. No config reloading after process start
3. `${VAR}` only supports exact placeholder values, not embedded interpolation
4. Sandbox runtime profiles like `configs/profiles/py-basic.yaml` are not yet loaded through this config system; runtime sandbox profiles are still defined in code under [swarmmind/sandbox/profiles.py](swarmmind/sandbox/profiles.py)

## Next Good Extensions

If you continue evolving this system, the most natural next steps are:

1. Load sandbox profile YAML files into `swarmmind.sandbox.profiles`
2. Add config profile selection such as `config.local.yaml`, `config.dev.yaml`
3. Add tests covering source precedence and env placeholder behavior
4. Document production deployment examples for `.env`, secrets dir, and containerized env vars
