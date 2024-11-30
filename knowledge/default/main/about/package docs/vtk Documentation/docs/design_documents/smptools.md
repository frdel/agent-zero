# Parallel Processing with VTK's SMP Framework
August 2022

## Contributors
Berk Geveci wrote the initial version of this document in 2013. The design and implementation of vtkSMPTools was strongly influenced by the [KAAPI thread scheduling system](https://www.researchgate.net/publication/221564735_KAAPI_A_thread_scheduling_runtime_system_for_data_flow_computations_on_cluster_of_multi-processors) and an associated Inria research report: [*VtkSMP: Task-based Parallel Operators for Accelerating VTK Filters*](https://hal.inria.fr/hal-00789814). Later contributors to this document include:
- Timothee Couble
- Charles Gueunet
- Will Schroeder
- Spiros Tsalikis

Also note that several blog posts have been written about vtkSMPTools:
- [Simple, Parallel Computing with vtkSMPTools](https://www.kitware.com/simple-parallel-computing-with-vtksmptools/)
- [VTK Shared Memory Parallelism Tools, 2021 updates](https://www.kitware.com/vtk-shared-memory-parallelism-tools-2021-updates/)
- [Ongoing VTK / ParaView Performance Improvements](https://www.kitware.com/ongoing-vtk-paraview-performance-improvements/)
- [VTK/ParaView Filters: Performance Improvements](https://www.kitware.com/vtk-paraview-filters-performance-improvements/)

## Introduction
The overarching objective of vtkSMPTools, the SMP (symmetric multiprocessing) framework, is to provide an infrastructure to simplify the development of shared memory parallel algorithms in VTK. In addition, vtkSMPTools defines a simple, abstract API that drives several threading backends such as std::thread, TBB (i.e., Intel's Threading Building Blocks template library); and OpenMP; as well as supporting a sequential backend for testing and debugging. To achieve these objectives, we have developed three simple constructs to support basic SMP functionality:

- Parallel building blocks / functions
- Thread local storage
- Atomic integers and associated operations. (Note, since C++11 this has been superseded by `std::atomic<>`. Also, `std::mutex` and `vtkAtomicMutex` are options.)

vtkSMPTools is extremely easy to use, ensuring that the major challenge of creating parallel algorithms is not one of implementation, but rather the design of good, threaded algorithms.  In the next sections we describe the basic concepts used in vtkSMPTools, and then demonstrate these concepts through example code. Of course, there are hundreds of vtkSMPTools implementations found in VTK which provide an excellent source of more complex examples. In the final section of this document we provide tips on how to design and implement  vtkSMPTools-based algorithms.

## Concepts

The following are several high-level concepts that will help you understand and use vtkSMPTools.

### The Age of Abundant Computing Cores
Many early computational algorithms were designed and implemented in an era of limited computing resources: typically a single CPU was available with rudimentary memory models. Such limitations typically led to a frugal approach to writing algorithms, in particular approaches that minimized CPU utilization. However modern computing architectures commonly have many cores with multiple execution threads per core, and memory models have expanded to include a hierarchy of data caches to retrieve frequently used data more quickly. Also, many developers are inclined to think in terms of *sequential* algorithmic operations, partly due to the way in which we were trained but also because managing multiple simultaneous processes can take a lot of work and programmers are often pressed for time. But with growing data sizes, increasing computational demands, and the abundance of computing threads; it's clear that parallel approaches are essential to creating responsive and impactful software tools. It's important that VTK developers conceive and implement performant parallel algorithms to ensure that the system remain vital into the future.

There are a variety of approaches to parallel computing, but two approaches - distributed computing and shared memory computing - are particularly relevant to VTK. In distributed computing, computational tasks are carried out in separate memory space and exchange information through message passing communication. In shared memory computing, information is exchanged through variables in shared memory space. Typically a flavor of MPI is used by VTK for distributed computing, plus VTK provides a variety of software constructs to support distributed computing. vtkSMPTools is used to implement shared memory computing with symmetric multiprocessing (SMP) approaches; i.e., where multiple processors are connected to a single, shared memory space. Distributed computing is more complex and scales best for extremely large data, while shared memory computing is simpler and works cell on single computers (desktop, laptop, mobile). Note that it is possible to combine distributed and shared computing in a VTK application.

Besides MPI (for distributed computing) and vtkSMPTools (shared memory parallelism, typically on CPUs), be aware that VTK leverages another parallel processing toolkit for computing accelerators (e.g., GPUs). [vtk-m](https://m.vtk.org/) is a toolkit of scientific visualization algorithms for emerging processor architectures, supporting fine-grained concurrency for data analysis and visualization algorithms. Depending on the application, vtk-m may be a preferred solution for extreme scale computing. It is possible to mix all three forms of parallel computing frameworks into a single VTK application.

### Fine- and Coarse-Grained Parallelism
When parallelizing an algorithm, it is important to first consider the "dimension" (i.e., the way in which data is accessed via threads) over which to parallelize it. For example, VTK's Imaging modules parallelize many algorithms by assigning subsets of the input image (VOIs) to a thread safe function which processes them in parallel. Another example is parallelizing over blocks of a composite dataset (such as an AMR dataset). We refer to these examples as coarse-grained parallelism. On the other hand, we can choose points or cells as a dimension over which to parallelize access to a VTK dataset. Many algorithms simply loop over cells or points and are relatively trivial to parallelize this way. Here we refer to this approach as fine-grained parallelism. Note that some algorithms fall into a gray area. For example, if we parallelize streamline generation over seeds, is it fine- or coarse-grained parallelism?

### Backends
The SMP framework provides a thin abstraction over a number of threading backends. Currently, we support four backends: Sequential (serial execution); C++ std::thread referred to as STDThread; TBB (based on Intel’s TBB); and OpenMP. Note that the Sequential backend is useful for debugging but is typically not used unless no other backend can be made to work on the target platform. As discussed in the following, it's possible to build VTK with multiple backends, and switch between them at run-time.

Backends are configured via CMake during the build process. Setting the CMake variables `VTK_SMP_ENABLE_OPENMP`, `VTK_SMP_ENABLE_SEQUENTIAL`, `VTK_SMP_ENABLE_STDTHREAD`, and `VTK_SMP_ENABLE_TBB` enables the inclusion of the appropriate SMP backend(s), and `VTK_SMP_IMPLEMENTATION_TYPE` can be used to select one of Sequential, OpenMP, TBB, and STDThread (this selects the default backend when VTK runs). Once VTK is built, setting the environment variable `VTK_SMP_BACKEND_IN_USE` can be used to select from multiple backends. (Note: `vtkSMPTools::SetBackend()` can be used from within a C++ application to select the backend as well -- for example `vtkSMPTools::SetBackend("TBB")` will select TBB.)

### Thread Safety in VTK
Probably the most important thing in parallelizing shared-memory algorithms is to make sure that all operations that occur in a parallel region are performed in a thread-safe way (i.e., avoid race conditions). Note that there is much in the VTK core functionality that is not thread-safe. The VTK community has an ongoing effort of cleaning this up and marking APIs that are thread-safe to use. At this point, probably the best approach is to double check by looking at the implementation. Also, we highly recommend using analysis tools such as ThreadSanitizer or Valgrind (with the Helgrind tool) to look for race conditions in problematic code.

When coding parallel algorithms, be especially wary of insidious execution side effects. Such side effects typically result in simultaneous execution of code. For example, invoking `Update()` on a filter shared by multiple threads is a bad idea since simultaneous updates to that filter is likely doomed to fail. Also, some methods like `vtkPolyData::GetCellNeighbors()` internally invoke the one-time operation `BuildLinks()` in order to generate topological information. Similarly, the `BuildLocator()` method found in point and cell locators may be called as a side effect of a geoemtric query such as `vtkDataSet::FindCell()`. In such cases, prior to threaded execution, affected classes should be "primed" by explicitly invoking methods that produce side effects (e.g., call `BuildLinks()` directly on the `vtkPolyData`; or manually call `BuildLocator()` prior to using methods that require a locator).

### Results Invariance
A significant challenge to writing good threaded algorithms is to insure that they produce the same output each time they execute. For example, a threaded sort operation may order *identical* set elements differently each time the sort is run depending on the order in which data is processed by different computing threads. (This is related to the C++ standard providing the `std::stable_sort` algorithm.) Even simple threaded operation such as summing a list of numbers can produce different results, since the order and partitioning of data during threading may result in round off effects. Since sequential algorithms implicitly order their operations, and threading typically does not do so (unless extensive use of locks, barriers, etc. are used), a sequential algorithm may produce different results than a threaded algorithm, and even across multiple runs threaded algorithms may produce results that vary across each run. Such behaviors are disturbing to users, and make testing difficult. In VTK, we aim to write algorithms that are results invariant.

### Show Me the Code
The vtkSMPTools class defined in `VTK\Common\Core\vtkSMPTools.h` provides detailed documentation and further implementation details. To find examples of vtkSMPTools in use, simply search for VTK C++ classes that include this header file.

## Implementation Overview
As mentioned previously, vtkSMPTools provides a few, simple programmatic building blocks; support for thread-local storage; and support for atomics. In this section we provide high-level descriptions of these building blocks. Then in the following section we provide implementation details.

### Functional Building Blocks
The core, functional building blocks of vtkSMPTools are as follows. See `vtkSMPTools.h` for details.
* `For(begin, end, functor)` - a for loop over the range [begin,end) executing the functor each time.
* `Fill(begin, end, value)` - assign the given value to the elements in range [begin,end) (a drop in replacement for `std::fill()`).
* `Sort(begin,end)` and `Sort(begin,end,compare)` - sort the elements in range [begin,end) using the optional comparison function (a drop in replacement for `std::sort()`).
* `Transform()` - a drop in replacement for `std::transform()`.

Note that the ranges [begin,end) may be expressed via integral (`vtkIdType`) types for example point or cell ids, or C++ iterators.

Of special interest is the `functor` invoked in the `For()` loop. The functor is a class/struct which requires defining the `void operator()(begin,end)` method. Given a range defined by `[begin, end)` and the functor, `For()` will call the functor’s `operator()`, usually in parallel, over a number of subranges of `[begin, end)`. The functor may also implement methods to initialize data associated with each thread (`void Initialize()`), and to composite the results of executing the `For()` loop into a final result (i.e., `void Reduce()`).

With these few building blocks, powerful threaded algorithms can easily be written. In many cases, the `For()` loop is all that is needed.

### Thread Local Storage
Often times parallel algorithms produce intermediate results that are combined to produce a final result. For example, to sum a long list of numbers, each thread may sum just a subset of the numbers, and when completed the intermediate sums from each thread can be combined to produce a final summation. So the ability to maintain intermediate data associated with each thread is valuable. This is the purpose of thread local storage.

Thread local storage is generally referred to memory that is accessed by one thread only. In the SMP framework, vtkSMPThreadLocal and vtkSMPThreadLocalObject enable the creation of objects local to executing threads. The main difference between the two is that vtkSMPThreadLocalObject makes it easy to manage vtkObject and subclasses by allocating and deleting them appropriately. Thread local storage almost always requires definition of the `Initialize()` and `Reduce()` methods to initialize local storage, and then combine it once the `For()` loop completes.

One important performance trick with thread local storage, is that temporary variables may be defined and then used in the execution of `operator()`. For example, instantiating temporary objects such as vtkGenericCell, vtkIdList, and other C++ containers or classes can be relatively slow. Sometimes it's much faster to create and initialize them once (when the thread is created), and then "reset" them in each invocation of `operator()`.

### Atomics
Another very useful tool when developing shared memory parallel algorithms is atomic integers. Atomic integers provide the ability to manipulate integer values in a way that can’t be interrupted by other threads. A very common use case for atomic integers is implementing global counters. For example, in VTK, the modified time (MTime) global counter and vtkObject’s reference count are implemented as atomic integers.

Prior to C++11, vtkSMPTools had an internal implementation for atomic integers. However, this implementation is now obsolete in favor of `std::atomic<>`. C++ also provides `std::mutex' and 'std::lock_guard<>`; and VTK provides a lightweight spinlock `vtkAtomicMutex` which may be faster than using mutexes.

## Implementation Examples
In the subsections below, we describe the SMP framework in more detail and provide examples of how it can be used.

### Functors and Parallel For
The `vtkSMPTools::For()` parallel for is the core computational construct of vtkSMPTools. It's use is as shown in the following example which evaluates points against a set of planes, and adjusts the planes to "bound" the points (see `vtkHull.cxx` and `VTK/Common/DataModel/Testing/Cxx/TestSMPFeatures.cxx`).
```
  vtkNew<vtkPoints> pts;
  pts->SetDataTypeToFloat();
  pts->SetNumberOfPoints(numPts);
  for ( auto i=0; i < numPts; ++i)
  {
    pts->SetPoint(i, vtkMath::Random(-1,1), vtkMath::Random(-1,1), vtkMath::Random(-1,1));
  }
```
Now define the functor:
```
struct HullFunctor
{
  vtkPoints *InPts;
  std::vector<double>& Planes;

  HullFunctor(vtkPoints *inPts, std::vector<double>& planes) : InPts(inPts), Planes(planes) {}

  void operator()(vtkIdType ptId, vtkIdType endPtId)
  {
    vtkPoints *inPts = this->InPts;
    std::vector<double>& planes = this->Planes;
    auto numPlanes = planes.size() / 4;

    for (; ptId < endPtId; ++ptId)
    {
      double v, coord[3];
      inPts->GetPoint(ptId, coord);
      for (size_t j = 0; j < numPlanes; j++)
      {
        v = -(planes[j * 4 + 0] * coord[0] + planes[j * 4 + 1] * coord[1] +
          planes[j * 4 + 2] * coord[2]);
        // negative means further in + direction of plane
        if (v < planes[j * 4 + 3])
        {
          planes[j * 4 + 3] = v;
        }
      }
    }
 }
}; //HullFunctor
```
To use the functor and invoke `vtkSMPTools::For()`:
```
  HullFunctor hull(pts,planes);
  vtkSMPTools::For(0,numPts, hull);
```
Note that same code can be conveniently and compactly defined inline via a C++ lambda function. Lambdas are particularly useful when thread local storage and/or local variable are not required.
```
  vtkSMPTools::For(0, numPts, [&](vtkIdType ptId, vtkIdType endPtId) {
    for (; ptId < endPtId; ++ptId)
    {
      double v, coord[3];
      pts->GetPoint(ptId, coord);
      for (auto j = 0; j < numPlanes; j++)
      {
        v = -(planes[j * 4 + 0] * coord[0] + planes[j * 4 + 1] * coord[1] +
          planes[j * 4 + 2] * coord[2]);
        // negative means further in + direction of plane
        if (v < planes[j * 4 + 3])
        {
          planes[j * 4 + 3] = v;
        }
      }
    }
  }); // end lambda
```
With alternative signatures for `For()` it is possible to provide a grain parameter. Grain is a hint to the underlying backend about the coarseness of the typical range when parallelizing a for loop. If you don’t know what grain will work best for a particular problem, omit the grain specification and let the backend find a suitable grain. TBB in particular does a good job with this. Sometimes, you can eek out a little bit more performance by setting the grain just right. Too small, the task queuing overhead will be too much. Too little, load balancing will suffer.

### Thread Local Storage
Thread local storage is generally referred to memory that is accessed by one thread only. In the SMP framework, vtkSMPThreadLocal and vtkSMPThreadLocalObject enable the creation objects local to executing threads. The main difference between the two is that vtkSMPThreadLocalObject makes it easy to manage vtkObject and subclasses by allocating and deleting them appropriately.

Below is an example of thread local objects in use. This example computes the bounds of a set of points represented by a vtkFloatArray. Note in particular the introduction of the `Initialize()` and `Reduce()` methods:
```
using BoundsArray = std::array<double,6>;
using TLS = vtkSMPThreadLocal<BoundsArray>;

struct BoundsFunctor
{
  vtkFloatArray* Pts;
  BoundsArray Bounds;
  TLS LocalBounds;

  BoundsFunctor(vtkFloatArray *pts) : Pts(pts) {}

  // Initialize thread local storage
  void Initialize()
  {
    // The first call to .Local() will create the array,
    // all others will return the same.
    std::array<double,6>& bds = this->LocalBounds.Local();
    bds[0] = VTK_DOUBLE_MAX;
    bds[1] = -VTK_DOUBLE_MAX;
    bds[2] = VTK_DOUBLE_MAX;
    bds[3] = -VTK_DOUBLE_MAX;
    bds[4] = VTK_DOUBLE_MAX;
    bds[5] = -VTK_DOUBLE_MAX;
  }

  // Process the range of points [begin,end)
  void operator()(vtkIdType begin, vtkIdType end)
  {
    BoundsArray& lbounds = this->LocalBounds.Local();
    float* x = this->Pts->GetPointer(3*begin);
    for (vtkIdType i=begin; i<end; i++)
    {
      lbounds[0] = (x[0] < lbounds[0] ? x[0] : lbounds[0]);
      lbounds[1] = (x[0] > lbounds[1] ? x[0] : lbounds[1]);
      lbounds[2] = (x[1] < lbounds[2] ? x[1] : lbounds[2]);
      lbounds[3] = (x[1] > lbounds[3] ? x[1] : lbounds[3]);
      lbounds[4] = (x[2] < lbounds[4] ? x[2] : lbounds[4]);
      lbounds[5] = (x[2] > lbounds[5] ? x[2] : lbounds[5]);

      x += 3;
    }
  }

  // Composite / combine the thread local storage into a global result.
  void Reduce()
  {
    this->Bounds[0] = VTK_DOUBLE_MAX;
    this->Bounds[1] = -VTK_DOUBLE_MAX;
    this->Bounds[2] = VTK_DOUBLE_MAX;
    this->Bounds[3] = -VTK_DOUBLE_MAX;
    this->Bounds[4] = VTK_DOUBLE_MAX;
    this->Bounds[5] = -VTK_DOUBLE_MAX;

    using TLSIter = TLS::iterator;
    TLSIter end = this->LocalBounds.end();
    for (TLSIter itr = this->LocalBounds.begin(); itr != end; ++itr)
    {
       BoundsArray& lBounds = *itr;
       this->Bounds[0] = (this->Bounds[0] < lBounds[0] ? this->Bounds[0] : lBounds[0]);
       this->Bounds[1] = (this->Bounds[1] > lBounds[1] ? this->Bounds[1] : lBounds[1]);
       this->Bounds[2] = (this->Bounds[2] < lBounds[2] ? this->Bounds[2] : lBounds[2]);
       this->Bounds[3] = (this->Bounds[3] > lBounds[3] ? this->Bounds[3] : lBounds[3]);
       this->Bounds[4] = (this->Bounds[4] < lBounds[4] ? this->Bounds[4] : lBounds[4]);
       this->Bounds[5] = (this->Bounds[5] > lBounds[5] ? this->Bounds[5] : lBounds[5]);
    }
  }
}; // BoundsFunctor
```
Then to use the functor:
```
  vtkFloatArray* ptsArray = vtkFloatArray::SafeDownCast(pts->GetData());
  BoundsFunctor calcBounds(ptsArray);
  vtkSMPTools::For(0, numPts, calcBounds);
  std::array<double,6>& bds = calcBounds.Bounds;
```

A few things to note here:
* LocalBounds.Local() will return a new instance of a `std::vector<std::vector<double>>` per thread the first time it is called by that thread. All calls afterwards will return the same instance for that thread. Therefore, threads can safely access the local object over and over again without worrying about race conditions.
* The `Initialize()` method initializes the new instance of the thread local vector with invalid bound values.

So at the end of the threaded computation, the `LocalBounds` will contain a number of arrays, each that was populated by one thread during the parallel execution. These still need to be composited to produce the global bounds. This can be achieved by iterating over all thread local values and combining them in the `Reduce()` method as shown previously. Consequently the user can simply retrieve the final bounds by accessing `calcBounds.Bounds` once `vtkSMPTools::For()` completes execution. Note that, if the methods exist, `Initialize()` and `Reduce()` are invoked automatically by `vtkSMPTools::For()`.

Very important note: if you use more than one thread local storage object, don’t assume that the iterators will traverse them in the same order. The iterator for one may return the value from thread i with begin() whereas the other may return the value form thread j. If you need to store and access values together, make sure to use a struct or class to group them.

Thread local objects are immensely useful. Often, visualization algorithms want to accumulate their output by appending to a data structure. For example, the contour filter iterates over cells and produces polygons that it adds to an output vtkPolyData. This is usually not a thread safe operation. One way to address this is to use locks that serialize writing to the output data structure.

However, mutexes have a major impact on the scalability of parallel operations. Another solution is to produce a different vtkPolyData for each execution of the functor. However, this can lead to hundreds if not thousands of outputs that need to be merged, which is a difficult operation to scale. The best option is to use one vtkPolyData per thread using thread local objects. Since it is guaranteed that thread local objects are accessed by one thread at a time (but possibly in many consecutive functor invocations), it is thread safe for functors to keep adding polygons to these objects. The result is that the parallel section will produce only a few vtkPolyData, usually the same as the number of threads in the pool. It is much easier to efficiently merge these vtkPolyData.

### Atomic Integers
As mentioned previously, atomics should be represented by the C++ std::atomic<>. However, to provide a brief explanation of the importance of atomics we provide the following simple example.

```
int Total = 0;
std::atomic<vtkTypeInt32> TotalAtomic(0);
constexpr int Target = 1000000;
constexpr int NumThreads = 2;

VTK_THREAD_RETURN_TYPE MyFunction(void *)
{
  for (int i=0; i<Target/NumThreads; i++)
  {
    ++Total;
    ++TotalAtomic;
  }
  return VTK_THREAD_RETURN_VALUE;
}

// Now exercise atomics
vtkNew<vtkMultiThreader> mt;
mt->SetSingleMethod(MyFunction, NULL);
mt->SetNumberOfThreads(NumThreads);
mt->SingleMethodExecute();
std::cout << Total << " " << TotalAtomic.load() << endl;
```

When this program is executed, most of the time `Total` will be different (smaller) than `Target` whereas `TotalAtomic` will be exactly the same as `Target`. For example, a test run on a Mac prints: `999982 1000000`. This is because when the integer is not atomic, both threads can read the same value of `Total`, increment and write out the same value, which leads to losing one increment operation. Whereas, when ++ happens atomically, it is guaranteed that it will read, increment and write out `Total` all in one uninterruptible operation. When atomic operations are supported at hardware level, they are very fast.

## Tips
In this section, we provide some tips that we hope will be useful to those that want to develop shared memory parallel algorithms.

### Think about Thread Safety
First things first, it is essential to keep thread safety in mind. If the parallel section does not produce correct results consistently, there is not a lot of point in the performance improvement it produces. To create thread-safe algorithms, consider using common parallel design patterns. Also verify that the API you are using is thread safe under your particular application. While VTK continues to add additional thread-safe capabilities, there are still many booby traps to avoid.

### Analysis Tools Are Your Friend
The LLVM/Clang-based ThreadSanitizer is widely used to detect data races. Valgrind’s Helgrind is also a wonderful tool. Use these tools often. We developed the original backends mainly using Helgrind. Note that backends like TBB can produce many false positives; you may want to try different backends to reduce these. There are commercial tools with similar functionality, e.g., Intel’s Parallel Studio has static and dynamic checking.

### Debugging Tricks
Beyond using the analysis tools mentioned previously (e.g., ThreadSanitizer), there are some simple tricks that can be used to resolve programming issues relatively quickly. Firstly, switch between different backends. For example, if a program runs correctly when the backend is set to Sequential, but incorrectly when the backend is other than Sequential, it's likely that there is a race condition. Such broken code, when run repeatedly, while not always failing at the same point due to the variability of thread execution, will often fail at or near the same function, providing clues as to the location of the race. Also, empirically the STDThread backend seems to be most sensitive to race conditions. So make sure to test with more than one backend especially STDThread.

### Avoid Locks
Mutexes are expensive. Avoid them as much as possible. Mutexes are usually implemented as a table of locks by the kernel. They take a lot of CPU cycles to acquire. Specially, if multiple threads want to acquire them in the same parallel section. Use atomic integers if necessary. Try your best to design your algorithm without modifying the same data concurrently.

### Use Atomics Sparingly
Atomics are very useful and much more efficient that mutexes. However, overusing them may lead to performance issues. Try to design your algorithm in a way that you avoid locks and atomics. This also applies to using VTK classes that manipulate atomic integers such as MTime and reference count. Try to minimize operations that cause MTime or shared reference counts to change in parallel sections.

### Grain Can Be Important
In some situation, setting the right value for grain may be important. TBB does a decent job with this but there are situations where it can’t do the optimal thing. There are a number of documents on setting the grain size with TBB on the Web. If you are interested in tuning your code further, we recommend taking a look at some of them.

### Minimize Data Movement
This is true for serial parts of your code too but it is specially important when there are bunch of threads all accessing main memory. This can really push the limits of the memory bus. Code that is not very intensive computationally compared to how much memory it consumes is unlikely to scale well. Good cache use helps of course but may not be always sufficient. Try to group work together in tighter loops.

### Choose Computation over Memory
As mentioned earlier in this document, typically computation is much cheaper than data movement. As a result, it's a good idea to create compact data structures with minimal representational fat. Such data structures may require computation to extract important information: for example, a data structure that contains a vector 3-tuple need not represent the vector magnitude since this can be quickly computed. Depending on the number of times vector magnitude is needed, the cost of computing it is usually less than the cost of placing vector magnitude into memory. Of course, effects like this are a function of scale / data size and must be considered when designing applications.

### Multi-Pass Implementations
Parallel algorithms often require significant bookkeeping to properly partition and transform input data to output data. Trivial algorithms, such as mapping an input vector array of 3-tuples to an output scalar array of vector magnitudes, are easy to partition and map: for each vector tuple, a single scalar is produced; and if there are N tuples, there are N scalars. However, more complex algorithms such as building cell links (creating lists of cells connected to a point) or smoothing stencils (identifying points connected to each other via a cell edge) require an initial pass to determine the size of output arrays (and then to allocate the output), followed by another pass to actually populate the output arrays. While at first counterintuitive, it turns out that allocating a small number of large memory blocks is much, much faster than many dynamic allocations of small amounts of memory. This is one reason that a common implementation pattern for parallel algorithms is to use multiple data processing passes consisting of simple computing operations. Such an approach is quite different than many serial algorithms that often perform multiple, complex algorithmic steps for each input data item to be processed.

A variation of this approach is to use thread local storage to perform computation on a local range of input, store the result in thread local, and then reduce/composite the local storage into the global output. While this is problematic for many reasons (especially since data movement is needed to composite the output data), it still can be used to effectively partition and transform input data to the output, especially if the thread local storage is relatively small in size.

Whatever approach is used, parallel algorithms are often implemented using multiple passes. When designing parallel algorithms, it is important to think in terms of passes, and implement algorithms accordingly.

### Use Parallel Design Patterns
There are many parallel operations that are used repeatedly. Of course `for` loops and `fill()` are two obvious operations, but the `sort()` operation is more widely used than might be expected. Another is the prefix sum (or inclusive scan, or simply scan) typically used to build indices into data arrays. Become familiar with these and other parallel operations and the task of designing and implementing algorithms will be much easier.

## Parallel Is Not Always Faster
Threading introduces overhead into computation. As a result, threaded computation is not always faster than an equivalent serial operation. For example, `for` loops across a small number of data items can easily slow down computation due to **thread creation overhead**. A simple addition on each entry of an array may become a bottleneck if done using a too fine grain, due to **false sharing** (threads continuously invalidating other thread's cache). Even complex operations such as prefix sums across large amounts of data may be slower than serial implementations because of **synchronization issues**. For this reason, use threading sparingly to address data or computation of large scale. In VTK it is not uncommon to see code that switches between serial and parallel implementations based on input data size. For that reason, vtkSMPTools has an empirically determined THRESHOLD value that can be used by a developer to switch between serial and parallel implementations.

Different backends may have significantly performance characteristics as well. TBB for example uses a thread pool combined with task stealing to address load balancing challenges. Empirically at the time of writing, in some situations TBB can significantly outperform the STDThread backend especially in situations where task loads are highly variable. Of course this may change as std::thread implementations mature and evolve.
