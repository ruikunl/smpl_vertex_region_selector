# Demo Reference Assets

`public/` contains the committed, license-safe demo reference bundle used by fresh clones.

It includes:

- a procedural body mesh;
- 27,554 demo surface points;
- a `vertex_template_points.csv`;
- front/back/left/right reference PNGs;
- matching `vertex_id_map.npz` files.

These assets are for learning the UI and export workflow. They are not official SMPL assets and are not an
authoritative DensePose CSE alignment.

`generated/` is intentionally ignored. Use it for local regeneration or MakeHuman projection experiments:

```bash
smpl-make-demo-assets --output-dir assets/demo_reference/generated
smpl-project-alignment-to-mesh --output-dir assets/demo_reference/generated/makehuman_smpl_projected
```
