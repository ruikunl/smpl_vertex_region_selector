from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..region_io import empty_region_map, normalize_region_map
from ..schema import DEFAULT_REGIONS, VERTEX_COUNT


def _clean_ids(vertex_ids: Iterable[int]) -> list[int]:
    cleaned = {int(item) for item in vertex_ids}
    bad = [item for item in cleaned if item < 0 or item >= VERTEX_COUNT]
    if bad:
        raise ValueError(f"vertex ids out of range: {bad[:5]}")
    return sorted(cleaned)


@dataclass
class RegionState:
    regions: dict[str, list[int]] = field(default_factory=lambda: {name: [] for name in DEFAULT_REGIONS})
    current_region: str = "abdomen_front"
    selected_ids: set[int] = field(default_factory=set)
    hidden_regions: set[str] = field(default_factory=set)
    locked_regions: set[str] = field(default_factory=set)
    _undo: list[dict[str, list[int]]] = field(default_factory=list)
    _redo: list[dict[str, list[int]]] = field(default_factory=list)

    @classmethod
    def from_region_map(cls, payload: dict) -> "RegionState":
        normalized = normalize_region_map(payload)
        return cls(regions={name: list(ids) for name, ids in normalized["regions"].items()})

    def to_region_map(self, status: str = "draft") -> dict:
        payload = empty_region_map(status=status)
        payload["regions"].update({name: _clean_ids(ids) for name, ids in self.regions.items()})
        payload["region_sources"].update({name: "desktop_manual_selection" for name in self.regions})
        return normalize_region_map(payload, status=status)

    def snapshot(self) -> dict[str, list[int]]:
        return {name: list(ids) for name, ids in self.regions.items()}

    def _push_undo(self) -> None:
        self._undo.append(self.snapshot())
        self._redo.clear()

    def set_current_region(self, name: str) -> None:
        if name not in self.regions:
            self.regions[name] = []
        self.current_region = name

    def create_region(self, name: str) -> None:
        name = name.strip()
        if not name:
            raise ValueError("region name cannot be empty")
        if name in self.regions:
            self.current_region = name
            return
        self._push_undo()
        self.regions[name] = []
        self.current_region = name

    def rename_region(self, old_name: str, new_name: str) -> None:
        new_name = new_name.strip()
        if old_name not in self.regions:
            raise KeyError(old_name)
        if not new_name:
            raise ValueError("region name cannot be empty")
        if new_name in self.regions and new_name != old_name:
            raise ValueError(f"region {new_name!r} already exists")
        self._push_undo()
        self.regions[new_name] = self.regions.pop(old_name)
        if self.current_region == old_name:
            self.current_region = new_name

    def add_to_current(self, vertex_ids: Iterable[int]) -> None:
        if self.current_region in self.locked_regions:
            raise ValueError(f"region {self.current_region!r} is locked")
        incoming = set(_clean_ids(vertex_ids))
        if not incoming:
            return
        self._push_undo()
        existing = set(self.regions.setdefault(self.current_region, []))
        self.regions[self.current_region] = sorted(existing | incoming)

    def remove_from_current(self, vertex_ids: Iterable[int]) -> None:
        if self.current_region in self.locked_regions:
            raise ValueError(f"region {self.current_region!r} is locked")
        remove = set(_clean_ids(vertex_ids))
        if not remove:
            return
        self._push_undo()
        self.regions[self.current_region] = [item for item in self.regions.get(self.current_region, []) if item not in remove]

    def clear_current(self) -> None:
        if self.current_region in self.locked_regions:
            raise ValueError(f"region {self.current_region!r} is locked")
        self._push_undo()
        self.regions[self.current_region] = []

    def set_selection(self, vertex_ids: Iterable[int]) -> None:
        self.selected_ids = set(_clean_ids(vertex_ids))

    def undo(self) -> bool:
        if not self._undo:
            return False
        self._redo.append(self.snapshot())
        self.regions = self._undo.pop()
        return True

    def redo(self) -> bool:
        if not self._redo:
            return False
        self._undo.append(self.snapshot())
        self.regions = self._redo.pop()
        return True

    def toggle_hidden(self, region: str) -> None:
        if region in self.hidden_regions:
            self.hidden_regions.remove(region)
        else:
            self.hidden_regions.add(region)

    def toggle_locked(self, region: str) -> None:
        if region in self.locked_regions:
            self.locked_regions.remove(region)
        else:
            self.locked_regions.add(region)
