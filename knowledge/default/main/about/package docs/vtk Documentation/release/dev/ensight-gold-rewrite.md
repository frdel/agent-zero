## Rewrite reader for EnSight Gold files

There is a new version of the EnSight gold reader. This adds two classes, `vtkEnSightGoldCombinedReader` and `vtkEnSightSOSGoldReader`, to handle EnSight gold casefiles and SOS files, respectively.
This reader should have all of the functionality of the old reader, as well as supporting some things that the old reader did not. Notable differences between this reader and the old reader:

- No complicated class hierarchy. Hopefully this will be easier to maintain and figure out where problems are.
- There is an internal class, EnSightFile that handles all file operations and will handle ASCII, C binary, and Fortran binary. That makes it so the EnSightDataSet internal class doesn't have to care about what type of file is being read and can just focus on handling the logic around the different types of data (there are some rare cases where the way ASCII and binary are formatted in inconsistent ways, but for the most part EnSightDataSet doesn't need to care about file type).
- You can select which parts to load. By default, it will load all parts, but similar to loading selected arrays, you can load selected parts.
- Static geometry is cached.
- Outputs `vtkPartitionedDataSetCollection`

For parallel support, these readers take a different approach than the old readers. This reader makes the assumption that the user will want to stick to the decomposition of parts that already exists in their casefiles. The initial strategy for this reader assigns whole casefiles to the available processes as evenly as possible. This means that using the same number of processes as number of servers listed in the SOS file is the most efficient - each rank will read one casefile. If there are more processes than casefiles, some ranks will do no work, while if there are fewer processes than casefiles, some rank(s) will read more than one casefile. In the future, we will add a strategy that will consider the partition of a part in the casefile as an atomic unit, and those partitions could be more evenly distributed across ranks.
