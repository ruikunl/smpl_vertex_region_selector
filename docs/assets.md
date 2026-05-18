# Assets

## Required

`vertex_template_points.csv` is the minimum asset for this tool. It must contain
one row per `smpl_27554` vertex:

```text
vertex_id,atlas_u_norm,atlas_v_norm,mds0_norm,mds1_norm,mds2_norm
0,...
```

Only `vertex_id` is strictly required by the file format, but the desktop viewer
is much more useful when atlas or MDS coordinates are present.

Prepare it with:

```bash
smpl-prepare-assets --source-csv /path/to/vertex_template_points.csv
```

Build the aligned surface proxy with:

```bash
smpl-build-alignment \
  --vertex-csv assets/demo_reference/public/vertex_template_points.csv \
  --output-dir assets/processed/alignment
```

The builder first tries DensePose `SMPL_subdiv.mat` plus
`SMPL_SUBDIV_TRANSFORM.mat`, stored under ignored `assets/raw/densepose/`. That
path gives one 3D surface point for every `smpl_27554` vertex id.

Fresh clones already include a license-safe public demo bundle:

```text
assets/demo_reference/public/
  alignment_report.json
  surface_proxy.obj
  smpl_27554_surface_points.obj
  smpl_27554_to_surface_map.npz
  vertex_template_points.csv
  tri_views/*.png
  tri_views/*.vertex_id_map.npz
```

The GUI loads assets in this order:

1. `assets/processed/alignment/` if you have built local DensePose/SMPL assets.
2. `assets/demo_reference/public/` from the repository.
3. `assets/demo_reference/generated/` as an ignored local fallback.

To regenerate local demo assets without changing committed files:

```bash
smpl-make-demo-assets --output-dir assets/demo_reference/generated
```

Maintainers can refresh the committed public demo with:

```bash
smpl-make-demo-assets --output-dir assets/demo_reference/public
```

For a nicer local preview, project the local `smpl_27554` alignment onto a
MakeHuman CC0 target mesh:

```bash
smpl-project-alignment-to-mesh \
  --target-mesh makehuman:female_generic \
  --source-alignment assets/processed/alignment/smpl_27554_to_surface_map.npz \
  --output-dir assets/demo_reference/generated/makehuman_smpl_projected
```

This keeps vertex IDs from the source alignment and moves their display points
onto the target mesh surface. The MakeHuman mesh is CC0, but the projected
placement is derived from local alignment data, so the default output stays
ignored.

## Optional

You may provide an aligned body mesh to the desktop app. A mesh with exactly 27,554 vertices is
reported as `aligned_mesh`; other meshes are reported as `visual_reference` so
users do not accidentally export mesh-local IDs as DensePose CSE IDs.

## License note

SMPL models, DensePose data files/checkpoints, and some mesh assets may have
licenses that do not allow redistribution. This project keeps those assets out
of git and documents where users should place their own local copies. The
official SMPL entry point is <https://smpl.is.tue.mpg.de/>; users must register,
accept the license, and keep downloaded files local.

See `docs/legal_assets.md` before publishing screenshots, generated assets, or
sample bundles. As a rule of thumb, `assets/demo_reference/public/` is for
public teaching; official SMPL `.pkl` files, DensePose raw `.mat/.pkl/.tar.gz`
files, and `assets/processed/alignment/` outputs built from them are local
validation artifacts.
