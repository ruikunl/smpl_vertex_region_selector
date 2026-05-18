from __future__ import annotations

from dataclasses import dataclass

MESH_NAME = "smpl_27554"
VERTEX_COUNT = 27554

DEFAULT_REGIONS = [
    "head",
    "neck",
    "chest_front",
    "abdomen_front",
    "pelvis_front",
    "upper_back",
    "lower_back",
    "left_upper_arm",
    "right_upper_arm",
    "left_lower_arm",
    "right_lower_arm",
    "left_hand",
    "right_hand",
    "left_upper_leg",
    "right_upper_leg",
    "left_lower_leg",
    "right_lower_leg",
    "left_foot",
    "right_foot",
]

REGION_COLORS = {
    "head": (255, 210, 90),
    "neck": (255, 180, 120),
    "chest_front": (60, 160, 255),
    "abdomen_front": (255, 85, 85),
    "pelvis_front": (220, 120, 255),
    "upper_back": (60, 210, 180),
    "lower_back": (70, 185, 90),
    "left_upper_arm": (255, 150, 50),
    "right_upper_arm": (255, 190, 50),
    "left_lower_arm": (185, 125, 255),
    "right_lower_arm": (145, 95, 230),
    "left_hand": (245, 110, 180),
    "right_hand": (220, 80, 150),
    "left_upper_leg": (80, 210, 255),
    "right_upper_leg": (70, 180, 235),
    "left_lower_leg": (145, 220, 80),
    "right_lower_leg": (110, 195, 70),
    "left_foot": (160, 145, 95),
    "right_foot": (130, 115, 80),
}


@dataclass(frozen=True)
class ValidationIssue:
    level: str
    message: str
