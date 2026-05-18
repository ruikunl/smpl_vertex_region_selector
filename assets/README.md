# Assets

This directory intentionally does not ship SMPL models, DensePose checkpoints,
or other large/licensed assets.

Put local-only assets here when running the selector:

```text
assets/raw/                         # Optional SMPL/DensePose geometry files, ignored.
assets/processed/alignment/         # Local true alignment outputs, ignored.
assets/demo_reference/public/       # Committed open-source-safe demo bundle.
assets/demo_reference/generated/    # Local regenerated demo bundle, ignored.
```

The minimum useful asset is a `vertex_template_points.csv` file with 27,554
rows and a `vertex_id` column. It may also contain normalized atlas or MDS
coordinates, for example:

```text
vertex_id,atlas_u_norm,atlas_v_norm,mds0_norm,mds1_norm,mds2_norm
0,0.36,0.44,0.79,0.05,0.06
```

Generate or copy it with:

```bash
smpl-prepare-assets --source-csv /path/to/vertex_template_points.csv
```

Fresh clones include `assets/demo_reference/public/vertex_template_points.csv`
and matching demo tri-view assets, so the desktop app can be tried immediately.
Those public demo files are procedural teaching assets, not official SMPL or
DensePose alignment outputs.
