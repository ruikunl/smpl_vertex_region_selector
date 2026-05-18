# SMPL/DensePose Alignment Assets

## 中文

当前工具默认的 MDS 点云只是 `smpl_27554` vertex id 的数学可视化，不是标准站姿人体。
为了更直觉地选择腹部、背部、大腿等区域，需要构建一个对齐可视层：

```bash
smpl-build-alignment \
  --vertex-csv assets/demo_reference/public/vertex_template_points.csv \
  --output-dir assets/processed/alignment
```

默认前置条件：

- 工具会下载或读取 DensePose 官方 `SMPL_subdiv.mat` 和 `SMPL_SUBDIV_TRANSFORM.mat` 到
  `assets/raw/densepose/`。
- 这两个文件用于把 seam-aware subdiv SMPL 顶点聚合成 27,554 个 `smpl_27554` vertex id，
  是当前推荐的 3D 对齐来源。

官方 SMPL 本地验证路径：

- 先在 [SMPL official website](https://smpl.is.tue.mpg.de/) 注册、下载并同意 license。
- 不要把下载的 zip、`.pkl` 或由其生成的真实 alignment 输出提交到仓库。
- 如果你已经从官网拿到了 zip，可以用本地安装命令抽取到 ignored 目录：


```bash
smpl-install-local-assets \
  --smpl-zip /path/to/SMPL_python_v.1.1.0.zip \
  --uv-zip /path/to/smpl_uv_20200910.zip

smpl-build-alignment \
  --vertex-csv assets/demo_reference/public/vertex_template_points.csv \
  --output-dir assets/processed/alignment
```

也可以把官方 SMPL Python 模型 `.pkl` 放到 `assets/raw/smpl/`，用于旧的 UV fallback 路线。
这些文件都在 `.gitignore` 范围内，不会随开源仓库分发。

输出：

```text
assets/processed/alignment/
  alignment_report.json
  smpl_27554_to_surface_map.npz
  surface_proxy.obj
  smpl_27554_surface_points.obj
  tri_view_manifest.json
  tri_views/
    front.png
    front.vertex_id_map.npz
    back.png
    back.vertex_id_map.npz
    left.png
    left.vertex_id_map.npz
    right.png
    right.vertex_id_map.npz
```

`vertex_id_map.npz` 是三视图选择的权威映射：背景是 `-1`，人体像素是 `smpl_27554`
vertex id。外部参考图可以作为视觉背景，但不能作为权威映射来源。
渲染出来的 PNG 是彩色人体 reference，可能带 ribs/pelvis/navel guides（肋骨、骨盆、
肚脐辅助线）。这些线只是帮助人眼定位躯干边界的 2D template reference lines，不是
DensePose/CSE/SMPL 的模型输出；选择和导出仍然只依赖同名 `vertex_id_map.npz`。
默认 guide 采用 `heuristic_anthropometry_v1`：肋骨线近似 lower rib / costal margin，
骨盆线近似 iliac crest，上下两者之间的中点作为腰腹参考。它参考的是常见人体测量
landmarks，而不是逐人解剖标注。

如果没有 SMPL 文件，命令不会崩溃，会写出 `alignment_report.json`，状态为 `missing_smpl`。
如果禁用下载且没有 `SMPL_subdiv` / SMPL fallback 文件，命令不会崩溃，会写出 missing report。

如果只是想试 GUI 和导出格式，不需要官方模型：

```bash
smpl-region-selector
```

fresh clone 已经包含 `assets/demo_reference/public/`；如果没有本地
`assets/processed/alignment/`，GUI 会自动加载这套开源 demo。public demo 使用 MakeHuman CC0
target mesh 和预制的 `smpl_27554` vertex placement，适合教学和 CI；`surface_proxy_aligned`
才是本地 SMPL/DensePose 验证后用于 DensePose CSE 预标注的映射层。

## English

The default MDS point cloud is only a mathematical visualization of
`smpl_27554` IDs. For intuitive body-part selection, build SMPL/DensePose
alignment assets with `smpl-build-alignment`. The generated tri-view
`vertex_id_map.npz` files are authoritative: background pixels are `-1`, body
pixels store the corresponding `smpl_27554` vertex ID.

The rendered reference PNGs may include ribs, pelvis, and navel guide lines.
These are manual 2D template reference lines for orientation only. They are not
model outputs, not part of the `vertex_id_map.npz` data, and not exported as
region definitions.
The default `heuristic_anthropometry_v1` guide places the rib line near the
lower rib/costal margin, the pelvis line near the iliac crest, and the waist
guide near the midpoint between those two landmarks.

The preferred alignment source is DensePose `SMPL_subdiv.mat` plus
`SMPL_SUBDIV_TRANSFORM.mat`, which gives a complete 27,554-vertex surface. Fresh
clones include `assets/demo_reference/public/` for a MakeHuman CC0 public demo.
Use `smpl-install-local-assets` only with local files you have downloaded from
<https://smpl.is.tue.mpg.de/> and are licensed to use; keep SMPL files,
DensePose raw assets, and `assets/processed/alignment/` outputs local.
