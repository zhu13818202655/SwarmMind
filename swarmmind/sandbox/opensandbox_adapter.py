"""OpenSandbox adapter implementation."""

from __future__ import annotations

import asyncio
import re
from datetime import timedelta
from urllib.parse import urlparse
from loguru import logger

from opensandbox.config import ConnectionConfig
from opensandbox import Sandbox
from opensandbox.models import WriteEntry

from swarmmind.sandbox.profiles import DEFAULT_PROFILES, SandboxProfile, normalize_sandbox_profile_name
from swarmmind.sandbox.provider import ExecResult, SandboxHandle, SandboxProvider, WriteFileEntry


class OpenSandboxAdapter(SandboxProvider):
    """OpenSandbox adapter implementation."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = "http://localhost:45698",
        create_retry_count: int = 3,
        create_retry_backoff_seconds: float = 1.0,
        request_timeout_seconds: int = 180,
        profiles: dict[str, SandboxProfile] | None = None,
    ) -> None:
        self._create_retry_count = create_retry_count
        self._create_retry_backoff_seconds = create_retry_backoff_seconds
        self._profiles = profiles or DEFAULT_PROFILES
        self._sandboxes: dict[str, Sandbox] = {}
        self._base_url = base_url.strip() or "http://localhost:45698"
        self._connection_config = self._build_connection_config(
            api_key=api_key,
            base_url=self._base_url,
            request_timeout_seconds=request_timeout_seconds,
        )

    async def create(self, profile: str, metadata: dict[str, str] | None = None) -> SandboxHandle:
        """Create a sandbox."""
        resolved_profile = normalize_sandbox_profile_name(profile)
        if resolved_profile not in self._profiles:
            raise ValueError(f"Unknown sandbox profile: {profile}")

        selected = self._profiles[resolved_profile]
        sandbox = await self._create_with_retry(selected, metadata or {})

        sandbox_id = self._get_sandbox_id(sandbox)
        self._sandboxes[sandbox_id] = sandbox
        return SandboxHandle(sandbox_id=sandbox_id, profile=resolved_profile, image=selected.image)

    async def run_command(self, sandbox_id: str, cmd: str, cwd: str | None = None) -> ExecResult:
        """Run a command in the sandbox."""
        sandbox = self._get_sandbox(sandbox_id)
        command = f"cd {cwd} && {cmd}" if cwd else cmd
        execution = await sandbox.commands.run(command)
        exit_code = self._extract_exit_code(execution)
        stderr = self._merge_logs(getattr(getattr(execution, "logs", None), "stderr", []))
        error = getattr(execution, "error", None)
        if error is not None:
            error_value = getattr(error, "value", "")
            error_traceback = getattr(error, "traceback", [])
            extra = "\n".join([str(x) for x in error_traceback if x])
            if error_value:
                stderr = f"{stderr}\n{error_value}".strip()
            if extra:
                stderr = f"{stderr}\n{extra}".strip()

        return ExecResult(
            exit_code=exit_code,
            stdout=self._merge_logs(getattr(getattr(execution, "logs", None), "stdout", [])),
            stderr=stderr,
        )

    async def write_files(self, sandbox_id: str, files: list[WriteFileEntry]) -> None:
        """Write files to the sandbox."""
        sandbox = self._get_sandbox(sandbox_id)
        write_entries = [WriteEntry(path=f.path, data=f.data, mode=f.mode) for f in files]
        await sandbox.files.write_files(write_entries)

    async def read_file(self, sandbox_id: str, path: str, *, encoding: str | None = "utf-8") -> str | bytes:
        """Read a file from the sandbox."""
        sandbox = self._get_sandbox(sandbox_id)
        files_api = sandbox.files
        try:
            if encoding is None:
                read_bytes = getattr(files_api, "read_bytes", None)
                if callable(read_bytes):
                    return await read_bytes(path)
                return await files_api.read_file(path, binary=True)
            return await files_api.read_file(path, encoding=encoding)
        except TypeError:
            content = await files_api.read_file(path)
            if encoding is None and isinstance(content, str):
                return content.encode("utf-8")
            return content

    async def kill(self, sandbox_id: str) -> None:
        """Kill a sandbox."""
        sandbox = self._sandboxes.pop(sandbox_id, None)
        if sandbox is None:
            return
        try:
            await sandbox.kill()
        finally:
            await sandbox.close()

    async def _create_with_retry(self, profile: SandboxProfile, metadata: dict[str, str]) -> Sandbox:
        """Create sandbox with retry."""
        last_exc: Exception | None = None
        for attempt in range(1, self._create_retry_count + 1):
            try:
                return await self._create_sandbox(profile, metadata)
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "OpenSandbox create attempt failed",
                    extra={
                        "sandbox_profile": profile.name,
                        "sandbox_image": profile.image,
                        "sandbox_base_url": self._base_url,
                        "attempt": attempt,
                        "max_attempts": self._create_retry_count,
                        "error_type": type(exc).__name__,
                    },
                    exc_info=exc,
                )
                if attempt < self._create_retry_count:
                    backoff = self._create_retry_backoff_seconds * (2 ** (attempt - 1))
                    await asyncio.sleep(backoff)

        error_detail = "unknown error" if last_exc is None else f"{type(last_exc).__name__}: {last_exc}"
        raise RuntimeError(
            "Failed to create sandbox after retries "
            f"(profile={profile.name}, image={profile.image}, base_url={self._base_url}, cause={error_detail})"
        ) from last_exc

    async def _create_sandbox(self, profile: SandboxProfile, metadata: dict[str, str]) -> Sandbox:
        """Create sandbox."""
        sanitized_metadata = self._sanitize_metadata(metadata)
        create_variants: list[dict[str, object]] = [
            {
                "image": profile.image,
                "entrypoint": profile.entrypoint,
                "resource": profile.resource_limits,
            },
            {
                "image": profile.image,
                "entrypoint": profile.entrypoint,
                "resource": None,
            },
        ]

        last_exc: Exception | None = None
        seen: set[tuple[str, str, str]] = set()

        for variant in create_variants:
            image = str(variant["image"])
            entrypoint = variant["entrypoint"]
            resource = variant["resource"] if isinstance(variant["resource"], dict) or variant["resource"] is None else None
            key = (image, str(entrypoint), str(resource))
            if key in seen:
                continue
            seen.add(key)

            common_kwargs = {
                "entrypoint": entrypoint,
                "timeout": timedelta(seconds=profile.timeout_seconds),
                "env": profile.env,
                "metadata": sanitized_metadata,
            }

            try:
                return await Sandbox.create(
                    image,
                    resource=resource,
                    connection_config=self._connection_config,
                    **common_kwargs,
                )
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "OpenSandbox create variant failed",
                    extra={
                        "sandbox_profile": profile.name,
                        "sandbox_image": image,
                        "sandbox_entrypoint": entrypoint,
                        "sandbox_resource": resource,
                        "sandbox_base_url": self._base_url,
                        "error_type": type(exc).__name__,
                    },
                    exc_info=exc,
                )
                continue

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("OpenSandbox create failed with all profile variants")

    @staticmethod
    def _build_connection_config(*, api_key: str | None, base_url: str, request_timeout_seconds: int) -> ConnectionConfig:
        """Build connection config."""
        normalized = base_url.strip()
        if not normalized:
            normalized = "http://localhost:45698"

        if "//" not in normalized:
            normalized = f"http://{normalized}"

        parsed = urlparse(normalized)
        protocol = parsed.scheme or "http"
        domain = parsed.netloc or parsed.path

        if not domain and parsed.path:
            path = parsed.path.strip("/")
            if path and path != "v1":
                domain = path

        return ConnectionConfig(
            api_key=api_key,
            domain=domain,
            protocol=protocol,
            request_timeout=timedelta(seconds=max(30, int(request_timeout_seconds))),
        )

    @classmethod
    def _sanitize_metadata(cls, metadata: dict[str, str]) -> dict[str, str]:
        sanitized = {
            cls._sanitize_label_component(key): cls._sanitize_label_component(value)
            for key, value in metadata.items()
        }
        if sanitized != metadata:
            logger.info(
                "Sanitized OpenSandbox metadata for label compatibility",
                extra={
                    "original_metadata": metadata,
                    "sanitized_metadata": sanitized,
                },
            )
        return sanitized

    @staticmethod
    def _sanitize_label_component(value: str) -> str:
        normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value).strip())
        normalized = re.sub(r"^[^A-Za-z0-9]+", "", normalized)
        normalized = re.sub(r"[^A-Za-z0-9]+$", "", normalized)
        if not normalized:
            return "na"
        if len(normalized) <= 63:
            return normalized

        truncated = normalized[:63]
        truncated = re.sub(r"[^A-Za-z0-9]+$", "", truncated)
        return truncated or "na"

    def _get_sandbox(self, sandbox_id: str) -> Sandbox:
        """Get sandbox by ID."""
        sandbox = self._sandboxes.get(sandbox_id)
        if sandbox is None:
            raise KeyError(f"Sandbox not found: {sandbox_id}")
        return sandbox

    @staticmethod
    def _merge_logs(entries: list[object]) -> str:
        """Merge log entries."""
        texts: list[str] = []
        for entry in entries:
            text = getattr(entry, "text", "")
            if text:
                texts.append(text)
        return "".join(texts)

    @staticmethod
    def _extract_exit_code(execution: object) -> int:
        """Extract exit code from execution."""
        for attr in ("exit_code", "exitCode"):
            value = getattr(execution, attr, None)
            if isinstance(value, int):
                return value

        error = getattr(execution, "error", None)
        if error is not None:
            raw = getattr(error, "value", None)
            try:
                return int(str(raw))
            except (TypeError, ValueError):
                return 1

        return 0

    @staticmethod
    def _get_sandbox_id(sandbox: Sandbox) -> str:
        """Get sandbox ID."""
        for attr in ("id", "sandbox_id"):
            value = getattr(sandbox, attr, None)
            if isinstance(value, str) and value:
                return value
        raise RuntimeError("OpenSandbox SDK did not return sandbox id")
