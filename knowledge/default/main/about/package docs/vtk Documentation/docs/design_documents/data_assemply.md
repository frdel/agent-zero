# Data Assembly

VTK 10.0 introduces a new mechanism for representing data hierarchies
using vtkPartitionedDataSetCollection and vtkDataAssembly. This document
describes the design details.

## Data Model

The design is based on three classes:

* `vtkPartitionedDataSet` is a collection of datasets (not to be confused with
  `vtkDataSet`).
* `vtkPartitionedDataSetCollection` is a collection of `vtkPartitionedDataSet`s.
* `vtkDataAssembly` defines the hierarchical relationships between items in a
  `vtkPartitionedDataSetCollection`.

### Partitioned Dataset

`vtkPartitionedDataSet` is simply a collection of datasets that are to be
treated as a logical whole. In data-parallel applications, each dataset may
represent a partition of the complete dataset on the current worker process,
rank, or thread. Each dataset in a `vtkPartitionedDataSet` is called a
**partition**, implying it is only a part of a whole.

All non-null partitions have similar field and attribute arrays. For example, if
a `vtkPartitionedDataSet` comprises of `vtkDataSet` subclasses, all will have
exactly the same number of point data/cell data arrays, with same names, same
number of components, and same data types.

### Partitioned Dataset Collection

`vtkPartitionedDataSetCollection` is a collection of `vtkPartitionedDataSet`.
Thus, it is simply a mechanism to group multiple `vtkPartitionedDataSet`
instances together. Since each `vtkPartitionedDataSet` represents a whole dataset
(not be confused with `vtkDataSet`), we can refer to each item in a
`vtkPartitionedDataSetCollection` as a **partitioned-dataset**.

Unlike items in the `vtkPartitionedDataSet`, there are no restrictions of consistency
between each items, partitioned-datasets, in the `vtkPartitionedDataSetCollection`.
Thus, in the multiblock-dataset parlance, each item in this collection can be thought
of as a block.

### Data Assembly

`vtkDataAssembly` is a means to define an hierarchical organization of items in a
`vtkPartitionedDataSetCollection`. This is literally a tree made up of named nodes.
Each node in the tree can have associated dataset-indices. For a `vtkDataAssembly` is
associated with a `vtkPartitionedDataSetCollection`,  each of the
dataset-indices is simply the index of a partitioned-dataset in the
`vtkPartitionedDataSetCollection`. A dataset-index can be associated with multiple nodes in
the assembly, however, a dataset-index cannot be associated with the same node more than once.

An assembly provides an ability to define a more complex view of the raw data blocks in
a more application-specific form. This is not much different than what could be achieved using simply
a `vtkMultiBlockDataSet`. However, there are several advantages to this separation of storage
(`vtkPartitionedDataSetCollection`) and organization (`vtkDataAssembly`). These will become clear as
we cover different use-cases.

While nodes in the data-assembly have unique ids, public facing algorithm APIs should not use them. For example
an extract-block filter that allows users to choose which blocks (rather partitioned-datasets)
to extract from vtkPartitionedDataSetCollection can expose an API that lets users provide
path-expression to identify nodes in the associated data-assembly using their names.

Besides accessing nodes by querying using their names, `vtkDataAssembly` also
supports a mechanism to iterate over all nodes in depth-first or breadth-first
order using a *visitor*. vtkDataAssemblyVisitor defines a API that can be
implemented to do custom action as each node in the tree is visited.

## Design Implications

1. Since `vtkPartitionedDataSet` is simply parts of a whole, there is no specific significance
   to the number of partitions. In distributed pipelines, for example, a `vtkPartitionedDataSet`
   on each rank can have arbitrarily many partitions. Furthermore, filters can add/remove
   partitions as needed. Since the `vtkDataAssembly` never refers to individual partitions, this has no
   implication to filters that use the hierarchical relationships.

2. When constructing `vtkPartitionedDataSetCollection` in distributed data-parallel cases,
   each rank should have exactly the same number of partitioned-datasets.
   In this case, each `vtkPartitionedDataSet` at a specific index across all ranks together is
   treated as a whole dataset. Similarly, the `vtkDataAssembly` on each should be identical.

3. When developing filters, it is worth considering whether the filter really is a
   `vtkPartitionedDataSetCollection` filter or simply a `vtkPartitionedDataSet`-aware
   filter that needs to operate on each `vtkPartitionedDataSet` individually. For example,
   typical multiblock-aware filters like ghost-cell-generation, data-redistribution, etc.,
   are simply `vtkPartitionedDataSet` filters. For `vtkPartitionedDataSet`-only filters,
   when the input is a `vtkPartitionedDataSetCollection`, the executive takes care of looping
   over each of the partitioned-dataset in the collection, thus simplifying the filter development.

4. Filters that don't change the number of partitioned-datasets in a
   vtkPartitionedDataSetCollection don't generally affect the relationships
   between the partitioned-datasets and hence can largely pass through the
   vtkDataAssembly. Only filter like extract-block that remove
   partitioned-datasets need to update the vtkDataAssembly. There too,
   vtkDataAssembly provides several convenience methods to update the tree with
   ease.

5. It is possible to develop a mapper that uses the `vtkDataAssembly`. Using
   APIs that let users use path-queries to specify rendering properties for
   various nodes, the mapper can support use-cases where the input structure
   keeps changing but the relationships remain largely intact.
   Since the same dataset-index can be associated with multiple nodes in a
   `vtkDataAssembly`, the mapper can effectively support scene-graph like
   capabilities where user can specify transforms, and other rendering
   parameters, while reusing the heavy datasets. The mapper can easily tell if
   a dataset has already been uploaded to the rendering pipeline since it will
   have the same id and indeed be the same instance even if is being visited
   through different branches in the tree.
