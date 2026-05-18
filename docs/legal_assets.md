# Legal Asset Boundaries

## 中文

这个项目刻意把代码和资产分开：

- 可以开源：Python 工具代码、MIT license、MakeHuman CC0 public demo bundle、AI 生成成人示例图、
  轻量 CSE example 输出、公开数据集下载脚本。
- 不随仓库分发：官方 SMPL Python 模型、DensePose 权重/数据资产、大型 mesh、用户自己的购买数据集图片。
- 默认 ignored：`assets/raw/`、`assets/processed/`、`assets/demo_reference/generated/`、`outputs/`。
- 可提交的默认 demo：`assets/demo_reference/public/`，它使用 MakeHuman CC0 target mesh 和
  `smpl_27554` vertex placement，不含 SMPL 模型文件、DensePose raw 资产、AI 生成人体照片或私有图片。

官方 SMPL Python 模型需要从 [SMPL official website](https://smpl.is.tue.mpg.de/) 注册下载，
通常只允许非商业科研、教育或艺术用途，不能把模型文件放进公开仓库。
本工具提供 `smpl-install-local-assets`，只是把你自己下载且有权使用的 zip 内容抽取到本机
ignored 目录，方便跑本地验证。

推荐的本地命令：

```bash
smpl-install-local-assets \
  --smpl-zip /path/to/SMPL_python_v.1.1.0.zip \
  --uv-zip /path/to/smpl_uv_20200910.zip

smpl-build-alignment \
  --vertex-csv assets/demo_reference/public/vertex_template_points.csv \
  --output-dir assets/processed/alignment
```

`smpl_uv` 文件的头部声明可能更宽松，但为了让开源边界简单清楚，本项目默认也不提交这些
文件。需要验证时把它们放在本地 `assets/raw/smpl_uv/` 即可。

DensePose 的 `SMPL_subdiv.mat` / `SMPL_SUBDIV_TRANSFORM.mat` 也只下载到本地 ignored 目录。
它们用于生成完整的 `smpl_27554` 选择可视层，不应作为仓库资产提交。

MakeHuman core assets / system assets 是公开 demo 的人体 mesh 来源：官方文档说明 core graphics
assets 使用 Creative Commons CC0。`assets/demo_reference/public/` 使用 MakeHuman CC0 target mesh
作为默认可视层，并包含一个已经准备好的 `smpl_27554` vertex placement。生成这套映射所需的本地
alignment 和生成代码不随仓库分发。

`assets/demo_reference/public/` 适合：

- README/CI 截图。
- 教学 vertex 选择流程。
- 验证 JSON/CSV/TXT 导出格式。

它不适合：

- 宣称为官方 SMPL 模型。
- 直接作为 DensePose CSE `smpl_27554` 精确对齐层。
- 评估腹部/背部等真实预标注质量。

真正用于 DensePose preannotation 的流程应该是：

1. 用户自己从官方渠道下载 SMPL。
2. 本地运行 `smpl-install-local-assets` 或手动放到 `assets/raw/smpl/`。
3. 本地运行 `smpl-build-alignment`。
4. 在 GUI 里看到 `surface_proxy_aligned` 状态后再选择和导出 region。

三层资产规则：

- `examples/`：AI 生成成人示例图、轻量 CSE 输出和 region map example，可以直接试 CSE inspector。
- `assets/demo_reference/public/`：MakeHuman CC0 public demo mesh/reference，可以提交。
- `assets/processed/alignment/`：用户本地生成的真实 DensePose/SMPL 对齐结果，继续 ignored。

## English

This repository separates code from licensed assets:

- Open-source friendly: Python code, MIT license, the MakeHuman CC0 public demo
  bundle, AI-generated adult examples, lightweight CSE example outputs, and
  public dataset download scripts.
- Not redistributed: official SMPL Python models, DensePose checkpoints, large
  meshes, and private or purchased dataset images.
- Ignored by default: `assets/raw/`, `assets/processed/`,
  `assets/demo_reference/generated/`, and `outputs/`.
- Committed demo assets: `assets/demo_reference/public/`, using a MakeHuman
  CC0 target mesh and `smpl_27554` vertex placement, without SMPL model files,
  DensePose raw assets, AI-generated people images, or private images.
- Committed examples: `examples/images/` and `examples/cse/`, containing
  AI-generated adult images and lightweight CSE maps/overlays/masks without raw
  DensePose dumps, model weights, SMPL files, or private images.

The official SMPL Python model should be downloaded from
<https://smpl.is.tue.mpg.de/> after registration and license acceptance. It is
generally limited to non-commercial research, education, or artistic use. Do not
commit or redistribute those model files from this project.
`smpl-install-local-assets` only extracts local files that you have downloaded
and are licensed to use into ignored local directories.

The public MakeHuman demo bundle is intended for teaching the UI workflow and
testing export formats. It is not an official SMPL model and is not an
authoritative DensePose CSE alignment.

The authoritative local workflow keeps SMPL files, DensePose raw data, and
`assets/processed/alignment/` outputs out of git. The public workflow uses
`examples/`, especially `examples/images/`, `examples/cse/`, and
`examples/region_map.example.json`, plus `assets/demo_reference/public/`.
