# DensePose CSE `vertex_map` and `smpl_27554` Vertex IDs

中文说明：

DensePose CSE 的目标不是直接输出“腹部”“背部”这样的语义类别，而是把图像里的
人体像素映射到一个固定人体表面模板。当前工具针对的是 `smpl_27554` 模板空间。
因此它既是 DensePose CSE 结果查看器，也是 `smpl_27554` vertex ID inspector：你可以从 2D 图像像素
反查 3D template vertex，也可以输入一组 vertex ID 在 3D/2D 模板视图中同步高亮。

一个典型的 `vertex_map.npz` 表示：

- shape: `(image_height, image_width)`
- dtype: integer
- background: `-1`
- foreground: `0..27553` 的 `smpl_27554` vertex ID

这意味着每个可见人体像素都有一个“它最接近模板表面哪个点”的编号。
如果你提前定义：

```json
{
  "abdomen_front": [100, 101, 102]
}
```

那么图像里的腹部候选 mask 就是：

```python
mask = np.isin(vertex_map, abdomen_front_vertex_ids)
```

## 为什么需要人工选 vertex？

`smpl_27554` 是表面位置空间，不是人体部位 taxonomy。腹部、腰部、下背、臀部、大腿边界
在业务上经常有不同定义，所以最稳妥的方式是让人一次性在模板上确认 region，然后把
这些 vertex ID 用于所有图片。

## English

DensePose CSE maps visible person pixels to a fixed human surface template. In
this tool the target space is `smpl_27554`, which has 27,554 vertices.
The app is therefore both a DensePose CSE result viewer and an `smpl_27554`
vertex ID inspector: image pixels can be mapped back to 3D template vertices,
and typed/imported vertex IDs can be highlighted in linked 3D and 2D views.

A CSE `vertex_map.npz` is a 2D integer array:

- background pixels are usually `-1`;
- visible body pixels store the nearest `smpl_27554` vertex ID;
- valid IDs are `0..27553`.

Body-part overlays are therefore lookup operations: define a set of template
vertex IDs, then select image pixels whose `vertex_map` value belongs to that
set.
