# Public Examples

## 中文

仓库提交三类轻量 public example：

```text
assets/demo_reference/public/
examples/images/*.png
examples/cse/vertex_maps/*.vertex_map.npz
examples/cse/overlays/*.cse_vertex_overlay.jpg
examples/cse/masks/*.foreground.png
examples/cse/cse_contact_sheet.jpg
examples/region_map.example.json
```

`assets/demo_reference/public/` 是默认 GUI demo。它使用 MakeHuman CC0 male target mesh，并包含
`smpl_27554` vertex placement、front/back/left/right 三视图 PNG，以及每个视图配套的
`vertex_id_map.npz`。

`examples/images/` 是 AI 生成的成人示例图；`examples/cse/` 是在本地 CUDA 设备上跑出的轻量
CSE 检查结果，只包含 `.vertex_map.npz`、overlay、foreground mask、manifest 和 summary，不包含
raw `.cse.pt`、模型权重、官方 SMPL 文件或私有数据集图片。

示例使用流程：

1. 运行 `smpl-region-selector`。
2. 导入 `examples/region_map.example.json` 或创建新 region。
3. 在 GUI 中先 `Load CSE Map` 加载 `examples/cse/vertex_maps/*.vertex_map.npz`。工具会默认高亮
   该 map 的所有有效 vertex。
4. 再 `Load CSE Image` 加载 `examples/images/` 中同名图片，用 `Load Mask/Points` 或手动选择
   收窄 selection。
5. 点击 `Add Selected` 后导出 region map，并用 `smpl-preview-overlay` 做本地 QA。

如果需要更多真实公开照片做本地 QA，请下载到 ignored 目录：

```bash
smpl-fetch-public-examples --output-dir assets/public_examples/coco_val2017_person
```

这些下载图片只用于本地验证，不应提交到仓库。

## English

The repository ships a lightweight public example bundle:

```text
assets/demo_reference/public/
examples/images/*.png
examples/cse/vertex_maps/*.vertex_map.npz
examples/cse/overlays/*.cse_vertex_overlay.jpg
examples/cse/masks/*.foreground.png
examples/cse/cse_contact_sheet.jpg
examples/region_map.example.json
```

`assets/demo_reference/public/` is the default GUI demo bundle. It uses a
MakeHuman CC0 male target mesh and includes `smpl_27554` vertex placement,
front/back/left/right reference PNGs, and matching `vertex_id_map.npz` files.

`examples/images/` contains AI-generated adult example images. `examples/cse/`
contains lightweight CSE outputs generated on a local CUDA machine: vertex maps,
overlays, foreground masks, manifests, and summaries. It does not include raw
`.cse.pt` dumps, model checkpoints, official SMPL files, or private dataset
images.

To try the CSE/Image inspector, load one bundled CSE `vertex_map.npz`, then load
the matching source image and refine the default highlighted selection.
Optional public dataset downloads should stay under ignored
`assets/public_examples/`.
