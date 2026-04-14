"""Group artifact JSON files by subtask id and sort them by creation time.

Usage examples:

    python scripts/group_artifacts_by_subtask.py \
        data/artifacts/1cb09df1-78f1-4dbd-8fea-300fb3e177ab

    python scripts/group_artifacts_by_subtask.py \
        data/artifacts/1cb09df1-78f1-4dbd-8fea-300fb3e177ab \
        --output-dir data/artifacts/1cb09df1-78f1-4dbd-8fea-300fb3e177ab_grouped \
        --clear-output
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


EMPTY_SUBTASK_PREFIX = "no-subtask"


@dataclass(slots=True)
class ArtifactEntry:
    """Normalized artifact record loaded from a JSON file."""

    source_path: Path
    artifact_id: str
    subtask_id: str | None
    created_at: datetime


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Group artifact JSON files by subtask id and sort them by created_at"
    )
    parser.add_argument("artifact_dir", help="Directory containing artifact JSON files")
    parser.add_argument(
        "--output-dir",
        help="Destination directory for grouped files. Defaults to <artifact_dir>_grouped.",
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="Move files instead of copying them into the grouped directory.",
    )
    parser.add_argument(
        "--clear-output",
        action="store_true",
        help="Delete the output directory first if it already exists.",
    )
    parser.add_argument(
        "--flatten-empty-subtask",
        action="store_true",
        help="Put empty subtask_id files into one folder instead of one folder per file.",
    )
    return parser


def sanitize_name(value: str) -> str:
    """Convert an arbitrary string to a filesystem-friendly name."""
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return sanitized or "group"


def normalize_subtask_id(raw_value: Any) -> str | None:
    """Normalize subtask ids so empty values become None."""
    if raw_value is None:
        return None
    normalized = str(raw_value).strip()
    return normalized or None


def parse_created_at(raw_value: str, source_path: Path) -> datetime:
    """Parse an ISO 8601 timestamp into a timezone-aware datetime."""
    normalized = raw_value.strip()
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"invalid created_at in {source_path}: {raw_value!r}") from exc

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def extract_created_at(payload: dict[str, Any], source_path: Path) -> datetime:
    """Extract the creation timestamp from supported field names."""
    candidate_values: list[Any] = [
        payload.get("created_at"),
        payload.get("Create at"),
        payload.get("create_at"),
    ]

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        candidate_values.extend(
            [
                metadata.get("created_at"),
                metadata.get("Create at"),
                metadata.get("create_at"),
            ]
        )

    for candidate in candidate_values:
        if isinstance(candidate, str) and candidate.strip():
            return parse_created_at(candidate, source_path)

    raise ValueError(f"missing created_at/Create at in {source_path}")


def load_artifact(path: Path) -> ArtifactEntry:
    """Load and normalize a single artifact JSON file."""
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError(f"artifact file must contain a JSON object: {path}")

    return ArtifactEntry(
        source_path=path,
        artifact_id=str(payload.get("id") or path.stem),
        subtask_id=normalize_subtask_id(payload.get("subtask_id")),
        created_at=extract_created_at(payload, path),
    )


def build_group_key(entry: ArtifactEntry, *, flatten_empty_subtask: bool) -> str:
    """Return a stable group key, treating empty subtask ids as unique groups by default."""
    if entry.subtask_id:
        return entry.subtask_id
    if flatten_empty_subtask:
        return EMPTY_SUBTASK_PREFIX
    return f"{EMPTY_SUBTASK_PREFIX}-{entry.artifact_id}"


def build_group_folder_name(group_index: int, entries: list[ArtifactEntry]) -> str:
    """Build the folder name for a grouped batch of artifact files."""
    first_entry = entries[0]
    label = first_entry.subtask_id or f"{EMPTY_SUBTASK_PREFIX}-{first_entry.artifact_id}"
    return f"{group_index:03d}_{sanitize_name(label)}"


def ensure_output_dir(output_dir: Path, clear_output: bool) -> None:
    """Prepare the output directory."""
    if output_dir.exists() and clear_output:
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def collect_json_files(artifact_dir: Path) -> list[Path]:
    """Collect top-level JSON files from the artifact directory."""
    return sorted(path for path in artifact_dir.iterdir() if path.is_file() and path.suffix == ".json")


def group_entries(
    entries: list[ArtifactEntry], *, flatten_empty_subtask: bool
) -> list[tuple[str, list[ArtifactEntry]]]:
    """Group entries by subtask id and order groups by earliest artifact creation time."""
    grouped: dict[str, list[ArtifactEntry]] = {}
    for entry in entries:
        group_key = build_group_key(entry, flatten_empty_subtask=flatten_empty_subtask)
        grouped.setdefault(group_key, []).append(entry)

    for grouped_list in grouped.values():
        grouped_list.sort(key=lambda item: (item.created_at, item.source_path.name))

    return sorted(
        grouped.items(),
        key=lambda item: (item[1][0].created_at, item[1][0].source_path.name),
    )


def materialize_groups(
    grouped_entries: list[tuple[str, list[ArtifactEntry]]],
    output_dir: Path,
    *,
    move_files: bool,
) -> list[dict[str, object]]:
    """Create grouped folders and copy or move the files into them."""
    summary: list[dict[str, object]] = []

    for group_index, (_, entries) in enumerate(grouped_entries, start=1):
        group_dir = output_dir / build_group_folder_name(group_index, entries)
        group_dir.mkdir(parents=True, exist_ok=True)

        files_summary: list[dict[str, str | None]] = []
        for file_index, entry in enumerate(entries, start=1):
            destination_name = f"{file_index:03d}_{entry.source_path.name}"
            destination_path = group_dir / destination_name
            if move_files:
                shutil.move(str(entry.source_path), str(destination_path))
            else:
                shutil.copy2(entry.source_path, destination_path)

            files_summary.append(
                {
                    "artifact_id": entry.artifact_id,
                    "original_name": entry.source_path.name,
                    "stored_name": destination_name,
                    "created_at": entry.created_at.isoformat().replace("+00:00", "Z"),
                    "subtask_id": entry.subtask_id,
                }
            )

        manifest = {
            "group_name": group_dir.name,
            "subtask_id": entries[0].subtask_id,
            "file_count": len(entries),
            "files": files_summary,
        }
        manifest_path = group_dir / "manifest.json"
        with manifest_path.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

        summary.append(manifest)

    return summary


def main() -> int:
    """Script entry point."""
    parser = build_parser()
    args = parser.parse_args()

    artifact_dir = Path(args.artifact_dir).expanduser().resolve()
    if not artifact_dir.exists() or not artifact_dir.is_dir():
        parser.error(f"artifact_dir does not exist or is not a directory: {artifact_dir}")

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else artifact_dir.with_name(f"{artifact_dir.name}_grouped")
    )

    json_files = collect_json_files(artifact_dir)
    if not json_files:
        parser.error(f"no JSON files found in artifact_dir: {artifact_dir}")

    entries = [load_artifact(path) for path in json_files]
    grouped_entries = group_entries(entries, flatten_empty_subtask=args.flatten_empty_subtask)

    ensure_output_dir(output_dir, args.clear_output)
    summary = materialize_groups(grouped_entries, output_dir, move_files=args.move)

    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "source_dir": str(artifact_dir),
                "group_count": len(summary),
                "groups": summary,
            },
            handle,
            ensure_ascii=False,
            indent=2,
        )
        handle.write("\n")

    print(f"Source directory: {artifact_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Groups created: {len(summary)}")
    print(f"Summary file: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())