"""Non-authorizing Public-only signal preview for the reviewed G013 generation."""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from app.h11_auto.contracts import FormalHorizon
from app.h11_auto.v4_actual_preparation_guard import (
    PREPARATION_ARTIFACT,
    require_clean_main,
    reviewed_files_digest,
)
from app.h11_auto.v4_gmo_contracts import V4GmoExecutionPolicy
from app.h11_auto.v4_gmo_generation import (
    V4_GMO_GENERATION_ARTIFACT,
    V4GmoFrozenGeneration,
    load_v4_gmo_frozen_generation,
)
from app.h11_manual.contracts import Horizon, map_probability
from app.h11_manual.short_model import (
    FEATURE_NAMES,
    MODEL_VERSION,
    ShortModelArtifact,
    _artifact_hash,
    predict_short_model,
)
from app.shadow.gmo_public import Candle, GmoPublicMarketDataClient

G013_PREVIEW_STATE_RELATIVE = Path("backend/market_data/h11_v4_g013_signal_preview")
G013_PREVIEW_MODEL_RELATIVE = Path("backend/market_data/h11_manual/short_model_artifact.json")
G013_PREVIEW_PUBLICATION_DELAY_SECONDS = 10
G013_PREVIEW_MAXIMUM_SIGNAL_AGE_SECONDS = 120
_PREREQUISITE_TOKEN = object()


class G013SignalPreviewError(RuntimeError):
    """Fixed safe preview failure; messages never contain provider data."""


@dataclass(frozen=True)
class _PreviewPrerequisite:
    token: object
    reviewed_files_digest: str
    generation: V4GmoFrozenGeneration


@dataclass(frozen=True)
class G013SignalPreviewReport:
    candidate_actionable: bool
    signal_fresh: bool
    signal_age_seconds: float

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "status": "G013_PUBLIC_SIGNAL_PREVIEW_NON_AUTHORIZING",
            "candidate_actionable": self.candidate_actionable,
            "signal_fresh": self.signal_fresh,
            "signal_age_seconds": self.signal_age_seconds,
            "public_get_count": 1,
            "direction_exposed": False,
            "probability_exposed": False,
            "price_exposed": False,
            "raw_response_retained": False,
            "credential_read": False,
            "private_api_read": False,
            "broker_write": False,
            "broker_post_count": 0,
            "authorization_granted": False,
            "activation_permit_issued": False,
            "actual_generation_consumed": False,
            "formal_signal_authorized": False,
        }

    def __bool__(self) -> bool:
        return False


def _load_prerequisite(*, repository: Path) -> _PreviewPrerequisite:
    repository = repository.resolve()
    require_clean_main(repository=repository)
    digest = reviewed_files_digest(repository=repository)
    artifact_path = repository / PREPARATION_ARTIFACT
    generation_path = repository / V4_GMO_GENERATION_ARTIFACT
    if (
        not artifact_path.is_file()
        or artifact_path.is_symlink()
        or not generation_path.is_file()
        or generation_path.is_symlink()
    ):
        raise G013SignalPreviewError("G013_PREVIEW_REVIEW_BOUNDARY_INVALID")
    try:
        evidence = json.loads(artifact_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise G013SignalPreviewError("G013_PREVIEW_REVIEW_BOUNDARY_INVALID") from error
    required_clear = (
        "focused_tests_passed",
        "related_tests_passed",
        "ruff_passed",
        "diff_check_passed",
        "danger_scan_passed",
        "architecture_review_clear",
        "safety_review_clear",
        "operations_review_clear",
    )
    if (
        not isinstance(evidence, dict)
        or evidence.get("schema") != "H11_V4_EXTERNAL_PREPARATION_EVIDENCE_V1"
        or evidence.get("status") != "REVIEWED_PREPARATION_ONLY_NO_BROKER_POST"
        or evidence.get("reviewed_files_digest") != digest
        or evidence.get("broker_post_authorized") is not False
        or evidence.get("activation_permit_issued") is not False
        or any(evidence.get(field) is not True for field in required_clear)
    ):
        raise G013SignalPreviewError("G013_PREVIEW_REVIEW_BOUNDARY_INVALID")
    try:
        generation = load_v4_gmo_frozen_generation(
            repository=repository,
            implementation_digest=digest,
        )
    except ValueError as error:
        raise G013SignalPreviewError("G013_PREVIEW_GENERATION_INVALID") from error
    if evidence.get("generation_manifest_digest") != generation.digest:
        raise G013SignalPreviewError("G013_PREVIEW_GENERATION_INVALID")
    if (
        generation.generation_label != "H11_AUTO_30M_20260717_G013"
        or generation.strategy_version != "SHORT_V1"
        or generation.selected_horizon != "30m"
        or generation.symbol != "USD_JPY"
        or generation.quantity_units != 1_000
        or generation.actual_post_authorized is not False
    ):
        raise G013SignalPreviewError("G013_PREVIEW_GENERATION_INVALID")
    return _PreviewPrerequisite(
        token=_PREREQUISITE_TOKEN,
        reviewed_files_digest=digest,
        generation=generation,
    )


def _execution_policy(generation: V4GmoFrozenGeneration) -> V4GmoExecutionPolicy:
    return V4GmoExecutionPolicy(
        strategy_version=generation.strategy_version,
        signal_config_hash=generation.signal_config_hash,
        selected_horizon=FormalHorizon.MINUTES_30,
        protection_contract_hash=generation.protection_contract_hash,
        broker_capability_evidence_hash=generation.broker_capability_evidence_hash,
    )


def _completed_slot(now_utc: datetime) -> datetime:
    if now_utc.tzinfo is None:
        raise G013SignalPreviewError("G013_PREVIEW_CLOCK_INVALID")
    current = now_utc.astimezone(UTC)
    if current.second < G013_PREVIEW_PUBLICATION_DELAY_SECONDS:
        raise G013SignalPreviewError("G013_PREVIEW_PUBLICATION_PENDING")
    return current.replace(second=0, microsecond=0) - timedelta(minutes=1)


def _safe_state_root(
    *, repository: Path, prerequisite: _PreviewPrerequisite
) -> Path:
    if prerequisite.token is not _PREREQUISITE_TOKEN:
        raise G013SignalPreviewError("G013_PREVIEW_PREREQUISITE_INVALID")
    base = repository.resolve() / G013_PREVIEW_STATE_RELATIVE
    current = repository.resolve()
    for part in G013_PREVIEW_STATE_RELATIVE.parts:
        current = current / part
        if current.is_symlink():
            raise G013SignalPreviewError("G013_PREVIEW_STATE_PATH_INVALID")
    root = base / (
        "review-"
        + prerequisite.reviewed_files_digest.removeprefix("sha256:")
        + "-generation-"
        + prerequisite.generation.digest.removeprefix("sha256:")
    )
    try:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
    except OSError as error:
        raise G013SignalPreviewError("G013_PREVIEW_STATE_PATH_INVALID") from error
    if root.is_symlink() or root.resolve() != root:
        raise G013SignalPreviewError("G013_PREVIEW_STATE_PATH_INVALID")
    return root


def _claim_slot(
    *,
    state_root: Path,
    slot_utc: datetime,
    prerequisite: _PreviewPrerequisite,
    model_input_digest: str,
) -> None:
    marker = state_root / f"slot-{slot_utc.strftime('%Y%m%dT%H%MZ')}-attempted.json"
    payload = json.dumps(
        {
            "schema": "H11_V4_G013_PUBLIC_SIGNAL_PREVIEW_ATTEMPT_V1",
            "status": "ATTEMPTED_NO_RETRY",
            "reviewed_files_digest": prerequisite.reviewed_files_digest,
            "generation_manifest_digest": prerequisite.generation.digest,
            "completed_m1_slot_utc": slot_utc.isoformat(),
            "model_input_digest": model_input_digest,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    try:
        descriptor = os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        directory_descriptor = os.open(state_root, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    except FileExistsError as error:
        raise G013SignalPreviewError("G013_PREVIEW_SLOT_ALREADY_ATTEMPTED") from error
    except OSError as error:
        raise G013SignalPreviewError("G013_PREVIEW_SLOT_CLAIM_FAILED") from error


def _parse_times(values: pd.Series) -> pd.Series:
    text = values.astype(str)
    numeric = text.str.fullmatch(r"\d{13}")
    parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns, UTC]")
    if numeric.any():
        parsed.loc[numeric] = pd.to_datetime(
            text.loc[numeric].astype("int64"), unit="ms", utc=True, errors="coerce"
        )
    if (~numeric).any():
        parsed.loc[~numeric] = pd.to_datetime(text.loc[~numeric], utc=True, errors="coerce")
    return parsed


def _normalize_frame(frame: pd.DataFrame, *, source: str) -> pd.DataFrame:
    required = ["time_utc", "open", "high", "low", "close"]
    if not set(required).issubset(frame.columns):
        raise G013SignalPreviewError(f"G013_PREVIEW_{source}_DATA_INVALID")
    result = frame.loc[:, required].copy()
    result["time_utc"] = _parse_times(result["time_utc"])
    for column in ("open", "high", "low", "close"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    numeric = result[["open", "high", "low", "close"]]
    valid = (
        result["time_utc"].notna()
        & numeric.apply(lambda column: column.map(math.isfinite)).all(axis=1)
        & (result["high"] >= result[["open", "close"]].max(axis=1))
        & (result["low"] <= result[["open", "close"]].min(axis=1))
        & (result["high"] >= result["low"])
    )
    if result.empty or not bool(valid.all()):
        raise G013SignalPreviewError(f"G013_PREVIEW_{source}_DATA_INVALID")
    duplicate = result[result.duplicated("time_utc", keep=False)]
    if not duplicate.empty:
        if source == "REMOTE":
            raise G013SignalPreviewError("G013_PREVIEW_REMOTE_DATA_INVALID")
        grouped = duplicate.groupby("time_utc")[["open", "high", "low", "close"]].nunique()
        if bool((grouped > 1).any(axis=None)):
            raise G013SignalPreviewError(f"G013_PREVIEW_{source}_DUPLICATE_CONFLICT")
    return result.drop_duplicates("time_utc", keep="last").sort_values("time_utc")


def _public_frame(candles: list[Candle]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "time_utc": candle.time,
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
            }
            for candle in candles
        ]
    )


def _digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _artifact_from_captured_bytes(value: bytes) -> ShortModelArtifact:
    raw = json.loads(value.decode("utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("invalid artifact")
    for key in (
        "feature_names",
        "feature_mean",
        "feature_scale",
        "weights_10m",
        "weights_30m",
    ):
        raw[key] = tuple(raw[key])
    artifact = ShortModelArtifact(**raw)
    if (
        artifact.version != MODEL_VERSION
        or artifact.feature_names != FEATURE_NAMES
        or artifact.config_hash != _artifact_hash(asdict(artifact), omit_hash=True)
    ):
        raise ValueError("invalid artifact")
    return artifact


def _read_model_input(
    *, repository: Path, expected_model_config_hash: str
) -> tuple[ShortModelArtifact, str, Path]:
    model_path = repository / G013_PREVIEW_MODEL_RELATIVE
    if not model_path.is_file() or model_path.is_symlink():
        raise G013SignalPreviewError("G013_PREVIEW_LOCAL_INPUT_INVALID")
    failed = False
    model_bytes = b""
    artifact: ShortModelArtifact | None = None
    try:
        model_bytes = model_path.read_bytes()
        artifact = _artifact_from_captured_bytes(model_bytes)
    except Exception:
        failed = True
    if failed or artifact is None:
        raise G013SignalPreviewError("G013_PREVIEW_LOCAL_INPUT_INVALID")
    if artifact.config_hash != expected_model_config_hash:
        raise G013SignalPreviewError("G013_PREVIEW_MODEL_CONFIG_MISMATCH")
    return artifact, _digest_bytes(model_bytes), model_path


def _require_model_input_unchanged(*, model_path: Path, expected_digest: str) -> None:
    failed = False
    actual_digest = ""
    try:
        actual_digest = _digest_bytes(model_path.read_bytes())
    except OSError:
        failed = True
    if failed or actual_digest != expected_digest:
        raise G013SignalPreviewError("G013_PREVIEW_MODEL_INPUT_CHANGED")


def _exact_remote_m1_window(*, remote: pd.DataFrame, slot: datetime) -> pd.DataFrame:
    completed = remote[remote["time_utc"] <= slot].reset_index(drop=True)
    if len(completed) < 31:
        raise G013SignalPreviewError("G013_PREVIEW_REMOTE_HISTORY_INSUFFICIENT")
    window = completed.tail(31).reset_index(drop=True)
    timestamps = pd.to_datetime(window["time_utc"], utc=True, errors="coerce")
    if (
        timestamps.isna().any()
        or timestamps.duplicated().any()
        or timestamps.iloc[-1].to_pydatetime().astimezone(UTC) != slot
        or not bool((timestamps.diff().iloc[1:] == pd.Timedelta(minutes=1)).all())
    ):
        raise G013SignalPreviewError("G013_PREVIEW_REMOTE_WINDOW_INVALID")
    return window


def _actionable(probability: object) -> bool:
    invalid = False
    try:
        numeric = float(probability)
    except (TypeError, ValueError):
        invalid = True
        numeric = math.nan
    if invalid or not math.isfinite(numeric):
        raise G013SignalPreviewError("G013_PREVIEW_MODEL_INVALID")
    decision = map_probability(probability)
    value = getattr(decision, "value", decision)
    if value in ("BUY", "SELL", "買い", "売り"):
        return True
    if value in ("STAY", "NO_TRADE", "見送り"):
        return False
    raise G013SignalPreviewError("G013_PREVIEW_MODEL_INVALID")


def run_g013_signal_preview(
    *,
    repository: Path,
    now_utc: datetime | None = None,
    client_factory: Callable[[], GmoPublicMarketDataClient] = GmoPublicMarketDataClient,
) -> G013SignalPreviewReport:
    """Run one completed-slot observation without producing any authorization object."""

    repository = repository.resolve()
    prerequisite = _load_prerequisite(repository=repository)
    current = (now_utc or datetime.now(UTC)).astimezone(UTC)
    policy = _execution_policy(prerequisite.generation)
    if not policy.entry_time_allowed(now_utc=current):
        raise G013SignalPreviewError("G013_PREVIEW_ENTRY_WINDOW_BLOCKED")
    slot = _completed_slot(current)
    artifact, model_input_digest, model_path = _read_model_input(
        repository=repository,
        expected_model_config_hash=prerequisite.generation.signal_config_hash,
    )
    state_root = _safe_state_root(repository=repository, prerequisite=prerequisite)
    _claim_slot(
        state_root=state_root,
        slot_utc=slot,
        prerequisite=prerequisite,
        model_input_digest=model_input_digest,
    )

    client: GmoPublicMarketDataClient | None = None
    public_failed = False
    candles: list[Candle] = []
    try:
        client = client_factory()
        candles = client.fetch_candles(
            "USD_JPY",
            "M1",
            0,
            price_type="BID",
            date=current.strftime("%Y%m%d"),
        )
    except Exception:
        public_failed = True
    finally:
        if client is not None:
            try:
                client.client.close()
            except Exception:
                pass
    if public_failed:
        raise G013SignalPreviewError("G013_PREVIEW_PUBLIC_GET_FAILED_NO_RETRY")

    remote = _normalize_frame(_public_frame(candles), source="REMOTE")
    model_frame = _exact_remote_m1_window(remote=remote, slot=slot)
    age = (current - slot).total_seconds()
    if age < 0 or age > G013_PREVIEW_MAXIMUM_SIGNAL_AGE_SECONDS:
        raise G013SignalPreviewError("G013_PREVIEW_SIGNAL_STALE")

    _require_model_input_unchanged(
        model_path=model_path,
        expected_digest=model_input_digest,
    )
    row_indexes = model_frame.index[model_frame["time_utc"] == slot].tolist()
    if len(row_indexes) != 1:
        raise G013SignalPreviewError("G013_PREVIEW_REMOTE_SLOT_INVALID")
    model_failed = False
    probability: object = None
    try:
        probability = predict_short_model(
            artifact,
            model_frame,
            int(row_indexes[0]),
            Horizon.MINUTES_30,
        )
    except Exception:
        model_failed = True
    if model_failed:
        raise G013SignalPreviewError("G013_PREVIEW_MODEL_FAILED")
    candidate = _actionable(probability)
    return G013SignalPreviewReport(
        candidate_actionable=candidate,
        signal_fresh=True,
        signal_age_seconds=age,
    )
