# Fix scalar color override logic in vtkCompositePolyDataMapper

When you override the color of a block using `vtkCompositePolyDataMapper`, in order
for it to take effect, especially when the block has scalars, be sure to either disable
`ScalarVisibility` on that block or disable the global `ScalarVisibility` in the mapper.
This is consitent with the functioning of `vtkMapper` for a `vtkDataSet` input.

Consider this. Here, the mapper is instantiated and the color of `mesh`
is overriden to `redColor`.

```cpp
vtkNew<vtkCompositePolyDataMapper> mapper;
vtkNew<vtkCompositeDataDisplayAttributes> cda;
// ..
// override the color of `mesh`
cda->SetBlockColor(mesh, redColor);
// turn OFF scalar visibility for `mesh`,
// because the default global `ScalarVisibility` inherited from `vtkCompositePolyDataMapper` is ON.
cda->SetBlockScalarVisibility(mesh, false);
```

However, if your mapper turns OFF ScalarVisibility for some reason, you do not need to do anything extra.

```cpp
vtkNew<vtkCompositePolyDataMapper> mapper;
mapper->ScalarVisibilityOff();
vtkNew<vtkCompositeDataDisplayAttributes> cda;
// ..
// override the color of `mesh`
cda->SetBlockColor(mesh, redColor);
// OK, no need to turn OFF `ScalarVisibility`, because the global property is turned OFF.
```
