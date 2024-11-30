# Field Data as Time Meta-Data in VTK XML File Formats

As of VTK 8.2, VTK XML readers and writers support embedding time
meta-data as a field array. This is demonstrated best with an example:

```xml
<VTKFile type="PolyData" version="1.0" byte_order="LittleEndian" header_type="UInt64">
  <PolyData>
    <FieldData>
      <DataArray type="Float64" Name="TimeValue" NumberOfTuples="1">1.24
      </DataArray>
    </FieldData>
    ...
</VTKFile>
```

Here TimeValue is a regular double precision array that has a single value of 1.24.
The XML readers will treat this array in a special way. When they encounter this array
during the meta-data stage (`RequestInformation()`), they will read the value from
this array and generate a `vtkStreamingDemandDrivenPipeline::TIME_STEPS()` key
in the output information containing this value.

In addition, the XML writers will generate a field array of name TimeValue in the
output, if they encounter time value in their input (`vtkDataObject::DATA_TIME_STEP()`).
This is done even if the data does not have a TimeValue array. Furthermore, even such
an array exists, it will be replaced with one that contains the value from
`vtkDataObject::DATA_TIME_STEP()` to make sure that the value is consistent with the
pipeline value.

This change may appear pointless on its own as a single time value is not very useful.
Its main use is when reading file series as it is done by ParaView's file (time) series
readers.
