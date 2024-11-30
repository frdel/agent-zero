# VTK Legacy Reader/Writer Information Format

## Overview

The legacy vtk data file readers / writers store certain `vtkInformation`
entries that are set on `vtkAbstractArray`'s `GetInformation()` object. Support
is currently limited to numeric and string information keys, both single- and
vector-valued. Only the information objects attached to arrays are encoded.

## Array Metadata Blocks

A block of metadata may immediately follow the specification of an array.
Whitespace is permitted between the array data and the opening `METADATA` tag.
The metadata block is terminated by an empty line.

```
# vtk DataFile Version 4.1
vtk output
ASCII
DATASET UNSTRUCTURED_GRID
POINTS 6 float
0 0 0 1 0 0 0.5 1 0
0.5 0.5 1 0.5 -1 0 0.5 -0.5 1

METADATA
COMPONENT_NAMES
X%20coordinates
Y%20coordinates
Z%20coordinates
INFORMATION 8
NAME Double LOCATION TestKey
DATA 1
NAME DoubleVector LOCATION TestKey
DATA 3 1 90 260
NAME IdType LOCATION TestKey
DATA 5
NAME String LOCATION TestKey
DATA Test%20String!%0ALine2
NAME Integer LOCATION TestKey
DATA 408
NAME IntegerVector LOCATION TestKey
DATA 3 1 5 45
NAME StringVector LOCATION TestKey
DATA 3
First
Second%20(with%20whitespace!)
Third%20(with%0Anewline!)
NAME UnsignedLong LOCATION TestKey
DATA 9

CELLS 3 15
4 0 1 2 3
4 0 4 1 5
4 5 3 1 0

CELL_TYPES 3
10
10
10

CELL_DATA 3
FIELD FieldData 1
vtkGhostType 1 3 unsigned_char
0 1 1
METADATA
COMPONENT_NAMES
Ghost%20level%20information
INFORMATION 1
NAME UNITS_LABEL LOCATION vtkDataArray
DATA radians

```

As shown, a metadata block can have two sections, `COMPONENT_NAMES` and
`INFORMATION`. The `INFORMATION` tag is followed by the number of information
keys that follow.

### COMPONENT_NAMES

If the `METADATA` block contains the line `COMPONENT_NAMES`, the following lines
are expected to be encoded strings containing the names of each component. There
must be one line per component.

### INFORMATION

If the `METADATA` block contains the line `INFORMATION`, the number of information
keys is read from the INFORMATION line and `vtkInformation` data that follows is
parsed. The general form of a single valued information entry is:

```
NAME [key name] LOCATION [key location (e.g. class name)]
DATA [value]
```

A vector information key is generally represented as:

```
NAME [key name] LOCATION [key location (e.g. class name)]
DATA [vector length] [value0] [value1] [value2] ...
```

The exception is a string vector, which contains encoded entries separated by
newlines.

Specific examples of supported key types:

#### vtkInformationDoubleKey

```
NAME Double LOCATION TestKey
DATA 1
```

#### vtkInformationDoubleVectorKey

```
NAME DoubleVector LOCATION TestKey
DATA 3 1 90 260
```

#### vtkInformationIdTypeKey

```
NAME IdType LOCATION TestKey
DATA 5
```

#### vtkInformationStringKey

```
NAME String LOCATION TestKey
DATA Test%20String!%0ALine2
```

#### vtkInformationIntegerKey

```
NAME Integer LOCATION TestKey
DATA 408
```

#### vtkInformationIntegerVectorKey

```
NAME IntegerVector LOCATION TestKey
DATA 3 1 5 45
```

#### vtkInformationStringVectorKey

```
NAME StringVector LOCATION TestKey
DATA 3
First
Second%20(with%20whitespace!)
Third%20(with%0Anewline!)
```

#### vtkInformationUnsignedLongKey

```
NAME UnsignedLong LOCATION TestKey
DATA 9
```
