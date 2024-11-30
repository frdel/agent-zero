# VTK XML Reader/Writer Information Format

## Overview

The vtk xml data file readers / writers store certain `vtkInformation`
entries that are set on `vtkAbstractArray`'s `GetInformation()` object. Support
is currently limited to numeric and string information keys, both single- and
vector-valued. Only the information objects attached to arrays are written/read.

## Array Information

Array information is embedded in the `<DataArray>` XML element as a series of
`<InformationKey>` elements. The required attributes `name` and `location`
specify the name and location strings associated with the key -- for instance,
the `vtkDataArray::UNITS_LABEL()` key has `name="UNITS_LABEL"` and
`location="vtkDataArray"`. The `length` attribute is required for vector keys.

```{code-block} xml
:force: true
<DataArray [...]>
  <InformationKey name="KeyName" location="KeyLocation" [ length="N" ]>
    [...]
  </InformationKey>
  <InformationKey [...]>
    [...]
  </InformationKey>
  [...]
</DataArray>
```

Specific examples of supported key types:

### vtkInformationDoubleKey

```xml
<InformationKey name="Double" location="XMLTestKey">
  1
</InformationKey>
```

### vtkInformationDoubleVectorKey

```xml
<InformationKey name="DoubleVector" location="XMLTestKey" length="3">
  <Value index="0">
    1
  </Value>
  <Value index="1">
    90
  </Value>
  <Value index="2">
    260
  </Value>
</InformationKey>
```

### vtkInformationIdTypeKey

```xml
<InformationKey name="IdType" location="XMLTestKey">
  5
</InformationKey>
```

### vtkInformationStringKey

```xml
<InformationKey name="String" location="XMLTestKey">
  Test String!
Line2
</InformationKey>
```

### vtkInformationIntegerKey

```xml
<InformationKey name="Integer" location="XMLTestKey">
  408
</InformationKey>
```

### vtkInformationIntegerVectorKey

```xml
<InformationKey name="IntegerVector" location="XMLTestKey" length="3">
  <Value index="0">
    1
  </Value>
  <Value index="1">
    5
  </Value>
  <Value index="2">
    45
  </Value>
</InformationKey>
```

### vtkInformationStringVectorKey

```xml
<InformationKey name="StringVector" location="XMLTestKey" length="3">
  <Value index="0">
    First
  </Value>
  <Value index="1">
    Second (with whitespace!)
  </Value>
  <Value index="2">
    Third (with
newline!)
  </Value>
</InformationKey>
```

### vtkInformationUnsignedLongKey

```xml
<InformationKey name="UnsignedLong" location="XMLTestKey">
  9
</InformationKey>
```
