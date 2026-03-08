"""High-level service: run Python data analysis inside a sandbox."""

from __future__ import annotations

from dataclasses import dataclass
import json

from swarmmind.sandbox.provider import SandboxProvider, WriteFileEntry


@dataclass(slots=True)
class DataAnalysisRequest:
    task_id: str
    agent_id: str
    subtask_id: str
    rows: list[dict]


@dataclass(slots=True)
class DataAnalysisResult:
    task_id: str
    sandbox_id: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    result: dict


class DataAnalysisService:
    """Run deterministic data analysis logic inside an ephemeral Python sandbox."""

    def __init__(self, provider: SandboxProvider, *, profile: str = "data-medium") -> None:
        self._provider = provider
        self._profile = profile

    async def run(self, request: DataAnalysisRequest) -> DataAnalysisResult:
        metadata = {
            "task_id": request.task_id,
            "agent_id": request.agent_id,
            "subtask_id": request.subtask_id,
        }
        handle = await self._provider.create(profile=self._profile, metadata=metadata)
        sandbox_id = handle.sandbox_id

        try:
            await self._prepare_environment(sandbox_id)
            await self._write_inputs(sandbox_id, request.rows)

            run_result = await self._provider.run_command(
                sandbox_id,
                "python /tmp/run_analysis.py",
            )

            result_payload: dict = {}
            if run_result.exit_code == 0:
                raw = await self._provider.read_file(sandbox_id, "/tmp/result.json")
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                result_payload = json.loads(raw)

            return DataAnalysisResult(
                task_id=request.task_id,
                sandbox_id=sandbox_id,
                success=run_result.exit_code == 0,
                exit_code=run_result.exit_code,
                stdout=run_result.stdout,
                stderr=run_result.stderr,
                result=result_payload,
            )
        finally:
            await self._provider.kill(sandbox_id)

    async def _prepare_environment(self, sandbox_id: str) -> None:
        install = await self._provider.run_command(
            sandbox_id,
            "pip install --no-cache-dir pandas numpy",
        )
        if install.exit_code != 0:
            raise RuntimeError(f"Dependency install failed: {install.stderr}")

    async def _write_inputs(self, sandbox_id: str, rows: list[dict]) -> None:
        script = _build_analysis_script()
        files = [
            WriteFileEntry(path="/tmp/input.json", data=json.dumps(rows, ensure_ascii=False), mode=0o644),
            WriteFileEntry(path="/tmp/run_analysis.py", data=script, mode=0o644),
        ]
        await self._provider.write_files(sandbox_id, files)


def _build_analysis_script() -> str:
    return '''
import json
import pandas as pd

with open("/tmp/input.json", "r", encoding="utf-8") as fp:
    rows = json.load(fp)

df = pd.DataFrame(rows)

result = {
    "row_count": int(len(df)),
    "columns": list(df.columns),
}

if len(df) > 0:
    numeric_cols = list(df.select_dtypes(include=["number"]).columns)
    result["numeric_columns"] = numeric_cols
    if numeric_cols:
        stats = df[numeric_cols].describe().fillna(0).to_dict()
        result["stats"] = stats

    # Common business metric for sales-like datasets.
    if "sales" in df.columns and "profit" in df.columns:
        total_sales = float(df["sales"].sum())
        total_profit = float(df["profit"].sum())
        margin = (total_profit / total_sales) if total_sales else 0.0
        result["sales_summary"] = {
            "total_sales": total_sales,
            "total_profit": total_profit,
            "profit_margin": margin,
        }

with open("/tmp/result.json", "w", encoding="utf-8") as fp:
    json.dump(result, fp, ensure_ascii=False, indent=2)

print("analysis completed")
'''.strip()
