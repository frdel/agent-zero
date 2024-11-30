Changes in VTK 7.1          {#VTK-7-1-Changes}
==================

This page documents API and behavior changes between VTK 7.0 and
VTK 7.1

Pipeline Update Methods
-----------------------

The following methods were deprecated in VTK 7.1:

### vtkAlgorithm:

    int SetUpdateExtentToWholeExtent(int port);
    int SetUpdateExtentToWholeExtent();
    void SetUpdateExtent(int port,
                         int piece,int numPieces, int ghostLevel);
    void SetUpdateExtent(
      int piece,int numPieces, int ghostLevel);
    void SetUpdateExtent(int port, int extent[6]);
    void SetUpdateExtent(int extent[6]);

### vtkStreamingDemandDrivenPipeline:

    int SetUpdateExtentToWholeExtent(int port);
    static int SetUpdateExtentToWholeExtent(vtkInformation *);
    int SetUpdateExtent(int port, int extent[6]);
    int SetUpdateExtent(int port, int x0, int x1, int y0, int y1, int z0, int z1);
    static int SetUpdateExtent(vtkInformation *, int extent[6]);
    int SetUpdateExtent(int port,
                        int piece, int numPieces, int ghostLevel);
    static int SetUpdateExtent(vtkInformation *,
                               int piece, int numPieces, int ghostLevel);
    static int SetUpdatePiece(vtkInformation *, int piece);
    static int SetUpdateNumberOfPieces(vtkInformation *, int n);
    static int SetUpdateGhostLevel(vtkInformation *, int n);
    int SetUpdateTimeStep(int port, double time);
    static int SetUpdateTimeStep(vtkInformation *, double time);

The following new methods were added:

### vtkAlgorithm:

    int Update(int port, vtkInformationVector* requests);
    int Update(vtkInformation* requests);
    int UpdatePiece(int piece, int numPieces, int ghostLevels, const int extents[6]=0);
    int UpdateExtent(const int extents[6]);
    int UpdateTimeStep(double time,
        int piece=-1, int numPieces=1, int ghostLevels=0, const int extents[6]=0);

### vtkStreamingDemandDrivenPipeline:

    int Update(int port, vtkInformationVector* requests);

The main reason behind these changes is to make requesting a particular time step or a particular spatial subset (extent or pieces) during an update easier and more predictable. Prior to these changes, the following is the best way to request a subset during update:

    vtkNew<vtkRTAnalyticSource> source;
    // Set some properties of source here
    source->UpdateInformation();
    source->SetUpdateExtent(0, 5, 0, 5, 2, 2);
    source->Update();

Note that the following will not work:

    vtkNew<vtkRTAnalyticSource> source;
    // Set some properties of source here
    // source->UpdateInformation(); <-- this was commented out
    source->SetUpdateExtent(0, 5, 0, 5, 2, 2);
    source->Update();

This is because when the output of an algorithm is initialized, all request meta-data stored in its OutputInformation is removed. The initialization of the output happens during the first *RequestInformation*, which is why `UpdateInformation()` needs to be called before setting any request values. To make things more complicated, the following will also not work:

    vtkNew<vtkRTAnalyticSource> source;
    // Set some properties of source here
    source->UpdateInformation();
    source->SetUpdateExtent(0, 5, 0, 5, 2, 2);
    source->Modified();
    source->Update();

This is because during *RequestInformation*, the extent and piece requests are initialized to default values (which is the whole dataset) and *RequestInformation* is called during update if the algorithm has been modified since the last information update.

This necessary sequence of calls has been mostly tribal knowledge and is very error prone. To simplify pipeline updates with requests, we introduced a new set of methods. With the new API, our example would be:

    vtkNew<vtkRTAnalyticSource> source;
    int updateExtent[6] = {0, 5, 0, 5, 2, 2};
    // Set some properties of source here
    source->UpdateExtent(updateExtent);

To ask for a particular time step from a time source, we would do something like this:

    vtkNew<vtkExodusIIReader> reader;
    // Set properties here
    reader->UpdateTimeStep(0.5);
    // or
    reader->UpdateTimeStep(0.5, 1, 2, 1);

The last call asks for time value 0.5 and the first of two pieces with one ghost level.

The new algorithm also supports directly passing a number of keys to make requests:

    typedef vtkStreamingDemandDrivenPipeline vtkSDDP;
    vtkNew<vtkRTAnalyticSource> source;
    int updateExtent[6] = {0, 5, 0, 5, 2, 2};
    vtkNew<vtkInformation> requests;
    requests->Set(vtkSDDP::UPDATE_EXTENT(), updateExtent, 6);
    reader->Update(requests.GetPointer());

This is equivalent to:

    typedef vtkStreamingDemandDrivenPipeline vtkSDDP;
    vtkNew<vtkRTAnalyticSource> source;
    int updateExtent[6] = {0, 5, 0, 5, 2, 2};
    source->UpdateInformation();
    source->GetOutputInformation(0)->Set(vtkSDDP::UPDATE_EXTENT(), updateExtent, 6);
    reader->Update();

We expect to remove the deprecated methods in VTK 8.0.

Derivatives
-----------

VTK has a C/row-major ordering of arrays. The vtkCellDerivatives
filter was erroneously outputting second order tensors
(i.e. 9 component tuples) in Fortran/column-major ordering. This has been
fixed along with the numpy vector_gradient and strain functions.
Additionally, vtkTensors was removed as this class was only
used by vtkCellDerivatives and was contributing to the confusion.

vtkSMPTools
-----------

The following back-ends have been removed:
+ Simple: This is not a production level backend and was only used for debugging purposes.
+ Kaapi: This backend is no longer maintained.

vtkDataArray Refactor, vtkArrayDispatch and Related Tools
---------------------------------------------------------

The `vtkDataArrayTemplate` template class has been replaced by
`vtkAOSDataArrayTemplate` to distinguish it from the new
`vtkSOADataArrayTemplate`. The former uses Array-Of-Structs component ordering
while the latter uses Struct-Of-Arrays component ordering. These both derive
from the new `vtkGenericDataArray` template class and are an initial
implementation of native support for alternate memory layouts in VTK.

To facilitate working with these arrays efficiently, several new tools have
been added in this release. They are detailed \ref VTK-7-1-ArrayDispatch "here".

As part of the refactoring effort, several `vtkDataArrayTemplate` methods were
deprecated and replaced with new, const-correct methods with more meaningful
names.

The old and new method names are listed below:

+ `GetTupleValue` is now `GetTypedTuple`
+ `SetTupleValue` is now `SetTypedTuple`
+ `InsertTupleValue` is now `InsertTypedTuple`
+ `InsertNextTupleValue` is now `InsertNextTypedTuple`
