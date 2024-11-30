## Add vtkAppendPartitionedDataSetCollection

vtkAppendPartitionedDataSetCollection is a filter that appends input partitioned dataset
collections with the same number of partitions and assembly (if present) into a single
output partitioned dataset collection. Each partitioned dataset of the output partitioned
dataset collection will either have 1 partition (merging occurs) or the N partitions,
where N is the summation of the number of partitions of the corresponding partitioned
datasets of the input partitioned dataset collections. To select the mode of the append filter,
use the SetAppendMode method.
