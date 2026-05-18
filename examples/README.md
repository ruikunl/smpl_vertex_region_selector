# Examples

This directory contains a small public example bundle for trying the selector and CSE inspector.

Included:

- `images/*.png`: AI-generated adult example images.
- `cse/vertex_maps/*.vertex_map.npz`: lightweight CSE-style vertex maps generated on a local CUDA machine.
- `cse/overlays/*.cse_vertex_overlay.jpg`: visual overlays.
- `cse/masks/*.foreground.png`: foreground masks.
- `cse/cse_contact_sheet.jpg`: quick visual summary.
- `region_map.example.json`: a minimal region-map schema example.

Not included:

- raw DensePose `.pt` dumps;
- DensePose weights;
- official SMPL files;
- private or purchased dataset images.

The fastest way to try them:

```bash
smpl-region-selector
```

The app loads the MakeHuman CC0 public demo assets from
`assets/demo_reference/public/`. Then load a file from `cse/vertex_maps/` and the
matching image from `images/` to inspect the CSE/Image workflow.
