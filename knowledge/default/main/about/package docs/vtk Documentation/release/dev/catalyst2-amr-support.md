# Add support for AMReX derived overlapping AMR datasets in situ with Catalyst 2

This change allows AMReX-based simulation codes to pass data to ParaView Catalyst 2.0 directly using a new Catalyst protocol `amrmesh`.

From an AMReX-based simulation code, one can use the AMReX function `MultiLevelToBlueprint` to produce a compliant Conduit Node.

```C++
void MultiLevelToBlueprint (int n_levels,
                            const Vector<const MultiFab*> &mfs,
                            const Vector<std::string> &varnames,
                            const Vector<Geometry> &geoms,
                            Real time_value,
                            const Vector<int> &level_steps,
                            const Vector<IntVect> &ref_ratio,
                            conduit::Node &bp_mesh);
```

This node can then be fed to a Catalyst Conduit node as the data leaf for a Catalyst channel with the type set to `"amrmesh"`.

```JSON
catalyst: {
  state: {...},
  channels: {
    mesh: {
      type: "amrmesh",
      data: bp_mesh,
    }
  }
}
```

Catalyst will construct a `vtkOverlappingAMR` object from the described data in the Conduit Node.

A unit test has been added with a single rank with multiple AMR boxes. This code has been tested in parallel using the AMReX-based simulation code MFix-Exa, a CFD code, closed source at the time of writing.
