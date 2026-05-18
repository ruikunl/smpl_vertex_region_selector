# Test Plan

## 中文

这个测试计划只依赖仓库内的小文件、内置 AI 示例和测试临时目录，不要求提交 SMPL、DensePose
权重、公开数据集下载图片、CSE raw `.pt` 或任何私有数据集。

自动化检查：

- `pytest tests/test_privacy_guard.py tests/test_docs_links.py`：确认开源文档和源码没有泄漏私有路径，
  并且 README/docs 中的本地 Markdown 链接都能解析。
- `pytest tests/test_vertex_id_io.py`：用临时小数组验证 vertex id 文本、CSV、region map、CSE map、
  mask 和 points 的解析行为。
- `pytest tests/test_region_io.py tests/test_region_state_export.py`：验证 region map schema、重复 ID
  warning 和导出 bundle。
- `pytest tests/test_demo_assets.py tests/test_renderer_reference.py`：用合成点/图片验证 demo reference、
  已提交 public demo 资产和 2D `vertex_id_map.npz` 的基本有效性。
- `pytest tests/test_examples.py`：验证内置 example manifest、AI 示例图片、轻量 CSE vertex maps、
  overlays 和 masks 都存在且 vertex id 范围合法。

手动 GUI 检查：

1. 运行 `smpl-region-selector`，确认 fresh clone 能自动加载 `assets/demo_reference/public/`。
2. 可选运行 `smpl-make-demo-assets --output-dir assets/demo_reference/generated`，确认 ignored 本地
   regeneration 目录仍可用。
3. 导入 `examples/region_map.example.json` 或手工输入 `12, 55, 100-130`，确认 selection 只高亮，
   不会自动写入 region。
4. 加载 `examples/cse/vertex_maps/` 中任意一个 CSE `vertex_map.npz`。`Load CSE Map` 后，
   所有有效 vertex 应默认高亮；
   点击 `Add Selected` 后才写入当前 region。
5. 加载 `examples/images/` 中同名 CSE image，确认 2D overlay 与 3D selection 同步。
6. 检查 2D template reference 的 ribs/pelvis/navel guides 只作为视觉辅助线显示，不影响导出 ID。
7. 导出 `region_map.json` 后，用 `smpl-preview-overlay` 在本地样例上做人工 QA。

隐私和资产检查：

- 不提交 `assets/raw/`、`assets/processed/`、`assets/demo_reference/generated/`、
  `assets/public_examples/` 或 `outputs/` 下的本地资产。
- 确认 `assets/demo_reference/public/` 和 `examples/cse/vertex_maps/*.vertex_map.npz` 没有被
  `.gitignore` 屏蔽；确认 `assets/raw/`、`assets/processed/`、`assets/demo_reference/generated/`
  仍会被 ignore。
- 不在 README/docs/tests 中写入私有数据集路径、下载目录、授权模型文件名或无法再分发的样例图片。
- 内置 `examples/images/` 使用 AI 成人示例；公开数据集照片只通过
  [docs/public_examples.md](public_examples.md) 中的下载流程进入 ignored 本地目录。

## English

This plan avoids large or licensed assets. Automated tests use repository files,
bundled AI examples, and temporary arrays only.

Run lightweight documentation and privacy checks with
`pytest tests/test_privacy_guard.py tests/test_docs_links.py`. Run
`tests/test_vertex_id_io.py`, `tests/test_region_io.py`, and
`tests/test_region_state_export.py` for ID parsing and export behavior. Use
`tests/test_demo_assets.py` and `tests/test_renderer_reference.py` for synthetic
reference rendering checks.

For manual GUI QA, open `smpl-region-selector` in a fresh clone and confirm it
loads `assets/demo_reference/public/`, import `examples/region_map.example.json`,
load a bundled example CSE map from
`examples/cse/vertex_maps/`, confirm that all valid vertices are highlighted by
default, then commit only with `Add Selected`. The ribs, pelvis, and navel lines
in 2D references should remain visual guides only and must not affect exported
vertex IDs.
