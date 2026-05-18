from __future__ import annotations

import json
import pickle
import tarfile
import urllib.request
import warnings
from pathlib import Path
from typing import Any, Optional

import numpy as np

DENSEPOSE_UV_TAR_URL = "https://dl.fbaipublicfiles.com/densepose/densepose_uv_data.tar.gz"
SMPL_SUBDIV_URL = "https://dl.fbaipublicfiles.com/densepose/data/SMPL_subdiv.mat"
SMPL_SUBDIV_TRANSFORM_URL = "https://dl.fbaipublicfiles.com/densepose/data/SMPL_SUBDIV_TRANSFORM.mat"


class _ChumpyStub:
    """Minimal unpickle target for old SMPL files when chumpy is not installed."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.__dict__.update(kwargs)

    @property
    def r(self) -> Any:
        for key in ("_r", "x", "a", "data"):
            if key in self.__dict__:
                return self.__dict__[key]
        return None

    def __setstate__(self, state: Any) -> None:
        if isinstance(state, dict):
            self.__dict__.update(state)
        else:
            self.__dict__["state"] = state


class _SmplUnpickler(pickle.Unpickler):
    def find_class(self, module: str, name: str) -> Any:
        if module.startswith("chumpy"):
            return _ChumpyStub
        return super().find_class(module, name)


def find_smpl_model(raw_root: Path) -> Optional[Path]:
    candidates = sorted((raw_root / "smpl").glob("*.pkl"))
    candidates = sorted(
        candidates,
        key=lambda path: (
            "neutral" not in path.name.lower(),
            "male" not in path.name.lower(),
            "female" not in path.name.lower(),
            path.name,
        ),
    )
    if candidates:
        return candidates[0]
    return None


def _array_from_pickle_value(value: Any) -> np.ndarray:
    if hasattr(value, "r"):
        value = value.r
    return np.asarray(value)


def _load_smpl_pickle(path: Path) -> dict[str, Any]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        with path.open("rb") as handle:
            try:
                return pickle.load(handle, encoding="latin1")
            except ModuleNotFoundError as exc:
                if exc.name != "chumpy":
                    raise
        with path.open("rb") as handle:
            return _SmplUnpickler(handle, encoding="latin1").load()


def load_smpl_template(path: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    payload = _load_smpl_pickle(path)
    if "v_template" not in payload:
        raise ValueError(f"{path} does not contain v_template")
    vertices = _array_from_pickle_value(payload["v_template"]).astype(np.float32)
    faces_key = "f" if "f" in payload else "faces"
    if faces_key not in payload:
        raise ValueError(f"{path} does not contain SMPL faces")
    faces = _array_from_pickle_value(payload[faces_key]).astype(np.int32)
    if vertices.ndim != 2 or vertices.shape[1] != 3:
        raise ValueError(f"SMPL v_template must be Nx3, got {vertices.shape}")
    if faces.ndim != 2 or faces.shape[1] != 3:
        raise ValueError(f"SMPL faces must be Fx3, got {faces.shape}")
    meta = {"path": str(path), "vertex_count": int(vertices.shape[0]), "face_count": int(faces.shape[0])}
    return vertices, faces, meta


def ensure_densepose_uv(raw_root: Path, download: bool = True) -> Optional[Path]:
    densepose_dir = raw_root / "densepose"
    mat_path = densepose_dir / "UV_Processed.mat"
    if mat_path.exists():
        return mat_path
    if not download:
        return None
    densepose_dir.mkdir(parents=True, exist_ok=True)
    archive_path = densepose_dir / "densepose_uv_data.tar.gz"
    request = urllib.request.Request(DENSEPOSE_UV_TAR_URL, headers={"User-Agent": "smpl-vertex-region-selector/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response, archive_path.open("wb") as handle:
        handle.write(response.read())
    with tarfile.open(archive_path, "r:*") as tar:
        for member in tar.getmembers():
            if member.name.endswith("UV_Processed.mat"):
                member.name = "UV_Processed.mat"
                tar.extract(member, densepose_dir)
                break
    if not mat_path.exists():
        nested = next(densepose_dir.rglob("UV_Processed.mat"), None)
        if nested:
            nested.replace(mat_path)
    return mat_path if mat_path.exists() else None


def _download_if_needed(url: str, path: Path, download: bool) -> Optional[Path]:
    if path.exists():
        return path
    if not download:
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "smpl-vertex-region-selector/0.1"})
    with urllib.request.urlopen(request, timeout=120) as response, path.open("wb") as handle:
        handle.write(response.read())
    return path if path.exists() else None


def ensure_smpl_subdiv(raw_root: Path, download: bool = True) -> tuple[Optional[Path], Optional[Path]]:
    densepose_dir = raw_root / "densepose"
    subdiv_path = _download_if_needed(SMPL_SUBDIV_URL, densepose_dir / "SMPL_subdiv.mat", download)
    transform_path = _download_if_needed(
        SMPL_SUBDIV_TRANSFORM_URL,
        densepose_dir / "SMPL_SUBDIV_TRANSFORM.mat",
        download,
    )
    return subdiv_path, transform_path


def load_densepose_uv(path: Path) -> dict[str, np.ndarray]:
    try:
        from scipy.io import loadmat
    except Exception as exc:
        raise RuntimeError("scipy is required to read UV_Processed.mat; install with pip install -e '.[gui]'") from exc
    payload = loadmat(path)
    required = ["All_vertices", "All_Faces", "All_U_norm", "All_V_norm", "All_FaceIndices"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise ValueError(f"{path} is missing DensePose fields: {missing}")
    return {key: np.asarray(payload[key]) for key in required}


def load_smpl_subdiv(subdiv_path: Path, transform_path: Path) -> dict[str, np.ndarray]:
    try:
        from scipy.io import loadmat
    except Exception as exc:
        raise RuntimeError("scipy is required to read SMPL_subdiv.mat; install with pip install -e '.[gui]'") from exc
    subdiv = loadmat(subdiv_path)
    transform = loadmat(transform_path)
    required = ["vertex", "faces", "Part_ID_subdiv", "U_subdiv", "V_subdiv"]
    missing = [key for key in required if key not in subdiv]
    if missing:
        raise ValueError(f"{subdiv_path} is missing SMPL subdiv fields: {missing}")
    if "index" not in transform:
        raise ValueError(f"{transform_path} is missing SMPL subdiv transform field: index")
    return {
        "vertex": np.asarray(subdiv["vertex"]),
        "faces": np.asarray(subdiv["faces"]),
        "part_id": np.asarray(subdiv["Part_ID_subdiv"]),
        "u": np.asarray(subdiv["U_subdiv"]),
        "v": np.asarray(subdiv["V_subdiv"]),
        "index": np.asarray(transform["index"]),
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
