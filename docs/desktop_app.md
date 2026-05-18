# Desktop App

## 中文

`smpl-region-selector` 是跨平台 Python 桌面入口，用于完成 `smpl_27554` vertex region 选择。

安装：

```bash
# Use Python 3.10+.
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[gui]"
```

`.[gui]` 会安装桌面应用需要的 `PySide6`、`open3d`、`scipy` 和 `trimesh`。

如果使用 requirements 文件：

```bash
python -m pip install -r requirements-gui.txt
python -m pip install -e .
```

`requirements.txt` 默认也指向完整 GUI 依赖；CLI-only 依赖在 `requirements-core.txt`。

运行：

```bash
smpl-region-selector
```

打开指定 alignment/demo 目录：

```bash
smpl-region-selector --alignment-dir assets/demo_reference/public
```

交互：

- 左键拖拽：旋转视角。
- 鼠标中键或右键拖拽：移动视图。
- 鼠标滚轮：缩放。
- `Select` 模式或按住 Shift 左键：点击选择最近 vertex id，拖拽框选当前视图中的一组 vertex id。
- 3D 视图左上角的 `Select/Rotate/Move`：切换当前鼠标交互模式，当前模式会保持高亮。
- toolbar 中 `Front/Back/Left/Right/Top/Bottom`：切换标准视角。
- 三视图 tab：在 front/back/left/right 彩色 reference 上点击或框选，直接反查对应 vertex id。
- `Add Selected`：把当前选中 id 加入右侧当前 region。
- `Remove Selected`：从当前 region 删除当前选中 id。
- `Export`：导出 `region_map.json`, `region_map.csv`, `vertex_ids/*.txt`。
- `Open3D Preview`：打开 Open3D 窗口查看当前点云/mesh/region 颜色。

## CSE map 与 2D reference

`Load CSE Map` 接受 `.npz/.npy` 中的 `vertex_id` 或 `vertex_map` 二维数组。加载后会打开
`CSE/Image` tab，把所有有效 vertex（像素值 `>= 0` 且落在 `0..27553`）的唯一 ID 设为当前
高亮 selection，并用 cyan overlay 标出有效 CSE 像素。这个默认 selection 只是检查和编辑起点；
只有点击 `Add Selected` 才会写入当前 region。

`Load CSE Image` 用匹配尺寸的原图替换 CSE tab 背景，便于检查 pixel-to-template 映射。
`Load Mask/Points` 可以在已加载的 CSE map 上把二值 mask 或像素点 CSV 转成对应 vertex ID，
并同步到 3D selection。

front/back/left/right 的 2D template reference PNG 可能带 ribs/pelvis/navel guides。
这些肋骨、骨盆、肚脐辅助线只是渲染时画出的人工视觉参考，不是 DensePose/CSE/SMPL 的模型输出，
不参与 `vertex_id_map.npz`，也不会作为 region 导出。

## Mesh 对齐规则

- `aligned_mesh`：mesh 顶点数等于 27,554，可以视为 `smpl_27554` 对齐候选。
- `visual_reference`：mesh 顶点数不是 27,554，只能做视觉参考，不会导出 mesh-local vertex id。
- `point_cloud_only`：未加载 mesh，只显示 `smpl_27554` 点云。
- `makehuman_cc0_smpl_projected_demo`：MakeHuman CC0 public demo，用来学习选择/导出流程，不是官方
  DensePose 精确映射。
- `surface_proxy_aligned`：已加载由 SMPL/DensePose 构建的 surface proxy 和三视图映射。

三视图里的彩色人体只是视觉 reference；点击/框选实际读取同尺寸 `vertex_id_map.npz`。如果以后接入
外部正面/侧面/背面参考图，也必须保持这条规则。

## English

`smpl-region-selector` is the cross-platform Python desktop app. It keeps the
`smpl_27554` point cloud as the authoritative selectable object and treats body
meshes as aligned only when they have exactly 27,554 vertices. Otherwise, meshes
are visual references and their local vertex IDs are never exported as DensePose
CSE IDs.

The app loads assets in this order: `assets/processed/alignment/` first,
`assets/demo_reference/public/` second, and ignored
`assets/demo_reference/generated/` last. When `assets/processed/alignment`
exists, the app loads the generated surface proxy and front/back/left/right
`vertex_id_map.npz` files. Selecting in any view updates the same authoritative
`smpl_27554` vertex selection. The lower tri-view images are colored references;
selection still reads the paired `vertex_id_map.npz`.

`Load CSE Map` accepts `.npz/.npy` arrays named `vertex_id` or `vertex_map`.
After loading, the app highlights every valid unique vertex ID by default and
shows valid CSE pixels with an overlay in the `CSE/Image` tab. This is an
editing starting point only; the IDs are not committed to the current region
until the user clicks `Add Selected`.

The 2D template reference PNGs may include ribs, pelvis, and navel guide lines.
Those lines are manual visual aids rendered into the PNGs. They are not
DensePose, CSE, or SMPL model outputs, they are not part of the vertex ID map,
and they are never exported as region data.
The current guides use a simple anthropometry-inspired heuristic: lower
rib/costal margin, iliac crest, and the midpoint between them.

When official alignment assets are absent, the app loads the committed
MakeHuman CC0 public demo assets. That mode is for learning the UI and export
formats, not for DensePose-quality anatomical labeling.
