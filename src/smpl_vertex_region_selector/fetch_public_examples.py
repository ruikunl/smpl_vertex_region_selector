from __future__ import annotations

import argparse
import json
import shutil
import urllib.request
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw

COCO_TERMS_URL = "https://cocodataset.org/#termsofuse"
COCO_VAL2017_BASE = "http://images.cocodataset.org/val2017"
CC_BY_2_URL = "http://creativecommons.org/licenses/by/2.0/"

# Small COCO val2017 person-keypoint examples whose annotation metadata lists
# license id 4: Creative Commons Attribution 2.0. Images are downloaded locally
# for demos and should not be committed to this project.
COCO_CC_BY_PERSON_IMAGES = [
    {
        "id": 274460,
        "file_name": "000000274460.jpg",
        "license_name": "Attribution License",
        "license_url": CC_BY_2_URL,
        "flickr_url": "http://farm7.staticflickr.com/6236/6267475434_0c28897158_z.jpg",
        "person_keypoint_instances": 13,
    },
    {
        "id": 229849,
        "file_name": "000000229849.jpg",
        "license_name": "Attribution License",
        "license_url": CC_BY_2_URL,
        "flickr_url": "http://farm5.staticflickr.com/4098/4943602569_06eebef70f_z.jpg",
        "person_keypoint_instances": 12,
    },
    {
        "id": 559842,
        "file_name": "000000559842.jpg",
        "license_name": "Attribution License",
        "license_url": CC_BY_2_URL,
        "flickr_url": "http://farm7.staticflickr.com/6039/6248453792_987793d2f0_z.jpg",
        "person_keypoint_instances": 11,
    },
    {
        "id": 1000,
        "file_name": "000000001000.jpg",
        "license_name": "Attribution License",
        "license_url": CC_BY_2_URL,
        "flickr_url": "http://farm5.staticflickr.com/4115/4906536419_6113bd7de4_z.jpg",
        "person_keypoint_instances": 10,
    },
    {
        "id": 5001,
        "file_name": "000000005001.jpg",
        "license_name": "Attribution License",
        "license_url": CC_BY_2_URL,
        "flickr_url": "http://farm6.staticflickr.com/5298/5457068434_0929d78491_z.jpg",
        "person_keypoint_instances": 10,
    },
    {
        "id": 377723,
        "file_name": "000000377723.jpg",
        "license_name": "Attribution License",
        "license_url": CC_BY_2_URL,
        "flickr_url": "http://farm9.staticflickr.com/8354/8303563388_c0b3b1939a_z.jpg",
        "person_keypoint_instances": 10,
    },
]


def download(url: str, output: Path, force: bool = False) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not force:
        return
    request = urllib.request.Request(url, headers={"User-Agent": "smpl-vertex-region-selector/0.1"})
    with urllib.request.urlopen(request, timeout=45) as response, output.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def make_contact_sheet(image_paths: list[Path], output: Path, thumb_width: int = 260) -> None:
    if not image_paths:
        return
    thumbs = []
    for path in image_paths:
        image = Image.open(path).convert("RGB")
        ratio = thumb_width / max(1, image.width)
        thumb = image.resize((thumb_width, max(1, int(image.height * ratio))))
        canvas = Image.new("RGB", (thumb_width, thumb.height + 24), (245, 245, 245))
        canvas.paste(thumb, (0, 0))
        draw = ImageDraw.Draw(canvas)
        draw.text((6, thumb.height + 4), path.name, fill=(30, 30, 30))
        thumbs.append(canvas)
    cols = min(3, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    cell_h = max(item.height for item in thumbs)
    sheet = Image.new("RGB", (cols * thumb_width, rows * cell_h), (250, 250, 250))
    for idx, thumb in enumerate(thumbs):
        sheet.paste(thumb, ((idx % cols) * thumb_width, (idx // cols) * cell_h))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Download public COCO person examples for local demos.")
    parser.add_argument("--output-dir", type=Path, default=Path("assets/public_examples/coco_val2017_person"))
    parser.add_argument("--limit", type=int, default=6)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--manifest-only", action="store_true")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    items = COCO_CC_BY_PERSON_IMAGES[: max(0, args.limit)]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    downloaded: list[Path] = []
    manifest_items = []
    for item in items:
        image_url = f"{COCO_VAL2017_BASE}/{item['file_name']}"
        output = args.output_dir / item["file_name"]
        if not args.manifest_only:
            download(image_url, output, force=args.force)
            downloaded.append(output)
        manifest_items.append(
            {
                **item,
                "dataset": "COCO val2017",
                "image_url": image_url,
                "local_path": str(output),
            }
        )
    manifest = {
        "dataset": "COCO val2017 person examples",
        "terms_url": COCO_TERMS_URL,
        "note": (
            "Images are downloaded locally for demos and are not committed. "
            "COCO states that image use must follow the original Flickr terms."
        ),
        "items": manifest_items,
    }
    with (args.output_dir / "manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    if downloaded:
        make_contact_sheet(downloaded, args.output_dir / "contact_sheet.jpg")
    print(f"Wrote public example manifest to {args.output_dir / 'manifest.json'}")
    if downloaded:
        print(f"Downloaded {len(downloaded)} images to {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
