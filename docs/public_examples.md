# Public Examples

## 中文

仓库现在只提交两类轻量 public example：

```text
assets/demo_reference/public/
examples/region_map.example.json
```

`assets/demo_reference/public/` 是默认 GUI demo。它使用 MakeHuman CC0 target mesh，并包含
`smpl_27554` vertex placement、front/back/left/right 三视图 PNG，以及每个视图配套的
`vertex_id_map.npz`。这些文件用于学习 3D/2D 选点和 region 导出流程。

`examples/region_map.example.json` 只演示 region map 的 JSON 结构。

本仓库不再分发 AI 生成人体照片，也不再分发预计算 CSE example 输出。如果你要检查 CSE/Image
inspector，请加载你自己生成的：

```text
*.vertex_map.npz
source image
optional mask/points
```

GUI 中 `Load CSE Map` 支持 `.npz/.npy`，key 可以是 `vertex_id` 或 `vertex_map`，背景为
`-1`。加载后，所有合法 vertex id 会默认同步高亮到 3D view。

如果需要更多真实公开照片做本地 QA，请下载到 ignored 目录：

```bash
smpl-fetch-public-examples --output-dir assets/public_examples/coco_val2017_person
```

这些图片只用于本地验证，不应提交到仓库。

## English

The repository now ships only lightweight public examples:

```text
assets/demo_reference/public/
examples/region_map.example.json
```

`assets/demo_reference/public/` is the default GUI demo bundle. It uses a
MakeHuman CC0 target mesh and includes `smpl_27554` vertex placement,
front/back/left/right reference PNGs, and matching `vertex_id_map.npz` files.

The project no longer bundles AI-generated people images or precomputed CSE
example outputs. To test the CSE/Image inspector, load your own CSE
`vertex_map.npz`, source image, and optional mask or point CSV. Optional public
dataset downloads should stay under ignored `assets/public_examples/`.
