# Region Selection Workflow

## 中文

推荐流程：

1. 准备 `vertex_template_points.csv`。
2. 在桌面 GUI 中加载点云、demo reference 或对齐 surface proxy。
3. 从大区域开始标：躯干前面、躯干后面、上腿、下腿、手臂。
4. 再细分业务关键区域：`abdomen_front`, `lower_back`, `pelvis_front`。
5. 加载真实或公开样例的 CSE `vertex_map` 做检查。`Load CSE Map` 会默认高亮所有有效 vertex，
   用它确认该样本在模板上的覆盖范围；只有点击 `Add Selected` 才会写入当前 region。
6. 每次导出后用 `smpl-preview-overlay` 在本地图片上检查。
7. 如果 overlay 漏掉或错选明显，回到 GUI 调整 vertex。

判断标准：

- 选择必须覆盖 DensePose CSE 在目标样本中常投影到的 vertex。
- 宁可输出候选区域后续再被 parsing/衣物/遮挡规则过滤，也不要把明显不相关部位混进来。
- 对边界不确定的区域，可以单独建 `ignore` 或 `transition` region，避免硬标。
- 2D template reference 上的 ribs/pelvis/navel guides 只是人工视觉辅助线，不是模型输出，
  不应作为自动分割或导出依据。

## examples 快速演练

- 用 `examples/region_map.example.json` 熟悉导出 schema。
- 直接启动 GUI 使用仓库内置的 `assets/demo_reference/public/` license-safe demo reference。
- 使用你自己的 CSE `vertex_map.npz` 体验 CSE inspector：加载 map 后所有有效 vertex 会默认高亮，
  再加载同尺寸原图检查 2D/3D 映射。
- 需要更多图片 QA 时，用 `smpl-fetch-public-examples` 下载公开样例到 ignored 的
  `assets/public_examples/`，再用本地 CSE pipeline 生成匹配的 `vertex_map.npz`。
- GUI 中先 `Load CSE Map`，再 `Load CSE Image`，最后用 selection 工具或 `Load Mask/Points`
  收窄高亮 vertex 并导出。

## English

Start with broad regions, validate on real CSE vertex maps, then refine. The
template region map is a reusable prior, not a perfect semantic segmentation by
itself. For production preannotation, combine it with parsing, occlusion, and
quality-control rules.

Use `examples/region_map.example.json` as a small schema reference and your own
CSE `vertex_map.npz` files to try the CSE inspector. In the desktop app, loading
a CSE map highlights all valid vertices by default so you can inspect coverage
before committing IDs with `Add Selected`. The ribs, pelvis, and navel guide
lines in 2D template references are visual aids only; they are not model outputs
or export data.
