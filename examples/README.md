# Examples

This directory intentionally stays small.

Included:

- `region_map.example.json`: a minimal region-map schema example.

Not included:

- AI-generated people images;
- precomputed CSE outputs;
- raw DensePose `.pt` dumps;
- DensePose weights;
- official SMPL files;
- private or purchased dataset images.

The fastest way to try the selector:

```bash
smpl-region-selector
```

The app loads the MakeHuman CC0 public demo assets from
`assets/demo_reference/public/`. Import `region_map.example.json` or create your
own region, select vertices in the 3D/2D views, then export.

To test the CSE/Image inspector, load your own `vertex_map.npz` and matching
source image.
