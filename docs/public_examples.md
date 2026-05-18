# Public Example Images

## 中文

这个工具会开源，所以不要提交私有、购买或授权范围不清晰的人体照片。仓库内置的
`examples/images/` 是 AI 生成的成人示例图，`examples/cse/` 包含对应的轻量 CSE 输出：

```text
examples/images/*.png
examples/cse/manifest.json
examples/cse/vertex_maps/*.vertex_map.npz
examples/cse/overlays/*.cse_vertex_overlay.jpg
examples/cse/masks/*.foreground.png
examples/cse/cse_contact_sheet.jpg
```

这些文件用于开源教学和 GUI smoke，不包含 raw `.cse.pt`、模型权重、官方 SMPL 文件或私有数据集图片。

如果需要更多真实公开照片做额外 QA，请下载到 ignored 的本地目录：

```bash
smpl-fetch-public-examples --output-dir assets/public_examples/coco_val2017_person
```

当前脚本使用 COCO val2017 中带 person keypoint 标注的少量图片，并优先选择 annotation
metadata 中 license 为 `Attribution License` 的样例。脚本会写出：

```text
assets/public_examples/coco_val2017_person/
  manifest.json
  contact_sheet.jpg
  *.jpg
```

这些文件被 `.gitignore` 排除，只用于本地验证和截图生成。

## 示例使用流程

本仓库里的 `examples/region_map.example.json` 演示 region map 格式；`examples/images/` 和
`examples/cse/` 演示 CSE map 到 3D vertex 的检查流程。

1. 直接运行 `smpl-region-selector`，先用仓库内置的 `assets/demo_reference/public/` 熟悉选择和导出。
2. 在 GUI 中先 `Load CSE Map` 加载 `examples/cse/vertex_maps/*.vertex_map.npz`。工具会默认高亮
   该 map 的所有有效 vertex，便于检查覆盖范围。
3. 再 `Load CSE Image` 加载 `examples/images/` 中同名图片，用 `Load Mask/Points` 或手动选择
   收窄 selection。
4. 点击 `Add Selected` 后导出 region map，并用 `smpl-preview-overlay` 做本地 QA。
5. 需要更多公开照片时，再下载到 `assets/public_examples/coco_val2017_person` 并自行生成匹配的
   `vertex_map.npz` 或 `.npy`；不要提交这些下载图片。

重要说明：

- COCO annotations 和网站由 COCO Consortium 以 CC BY 4.0 发布。
- COCO 官方同时说明，COCO 不拥有图片版权，图片使用需要遵守 Flickr Terms of Use。
- 因此，开源仓库中不分发 COCO 图片，只保留下载脚本和 attribution manifest。

## English

Do not commit private, purchased, or unclear-license human images to this
project. The repository includes AI-generated adult examples in `examples/images/`
and lightweight CSE outputs in `examples/cse/` so users can try the inspector
without private data or licensed model files. The example bundle includes
`*.vertex_map.npz`, overlays, masks, a manifest, and a contact sheet, but not raw
`.cse.pt`, model checkpoints, official SMPL files, or private dataset images.

For additional local QA, download public examples into an ignored directory:

```bash
smpl-fetch-public-examples --output-dir assets/public_examples/coco_val2017_person
```

The script writes a manifest with source URLs, Flickr URLs, and license URLs.
COCO annotations are licensed by the COCO Consortium, but the images are owned by
their original creators and must follow Flickr terms. For that reason this
project ships the downloader, not the image files.

To test the full flow, use the bundled `assets/demo_reference/public/` demo
assets, load one `examples/cse/vertex_maps/*.vertex_map.npz` file first, then
load the matching `examples/images/*.png` image and refine the default
highlighted valid vertices before export. Public dataset downloads remain
optional and should stay under ignored `assets/public_examples/`.
