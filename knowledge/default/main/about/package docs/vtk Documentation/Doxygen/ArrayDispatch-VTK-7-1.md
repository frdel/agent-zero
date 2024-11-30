# vtkArrayDispatch and Related Tools

## Background

VTK datasets store most of their important information in subclasses of
`vtkDataArray`. Vertex locations (`vtkPoints::Data`), cell topology
(`vtkCellArray::Ia`), and numeric point, cell, and generic attributes
(`vtkFieldData::Data`) are the dataset features accessed most frequently by VTK
algorithms, and these all rely on the `vtkDataArray` API.

## Terminology

This page uses the following terms:

A __ValueType__ is the element type of an array. For instance, `vtkFloatArray`
has a ValueType of `float`.

An __ArrayType__ is a subclass of `vtkDataArray`. It specifies not only a
ValueType, but an array implementation as well. This becomes important as
`vtkDataArray` subclasses will begin to stray from the typical
"array-of-structs" ordering that has been exclusively used in the past.

A __dispatch__ is a runtime-resolution of a `vtkDataArray`'s ArrayType, and is
used to call a section of executable code that has been tailored for that
ArrayType. Dispatching has compile-time and run-time components. At
compile-time, the possible ArrayTypes to be used are determined and a worker
code template is generated for each type. At run-time, the type of a specific
array is determined and the proper worker instantiation is called.

__Template explosion__ refers to a sharp increase in the size of a compiled
binary that results from instantiating a template function or class on many
different types.

### vtkDataArray

The data array type hierarchy in VTK has a unique feature when compared to
typical C++ containers: a non-templated base class. All arrays containing
numeric data inherit `vtkDataArray`, a common interface that sports a very
useful API. Without knowing the underlying ValueType stored in data array, an
algorithm or user may still work with any `vtkDataArray` in meaningful ways:
The array can be resized, reshaped, read, and rewritten easily using a generic
API that substitutes double-precision floating point numbers for the array's
actual ValueType. For instance, we can write a simple function that computes
the magnitudes for a set of vectors in one array and store the results in
another using nothing but the typeless `vtkDataArray` API:

```cpp
// 3 component magnitude calculation using the vtkDataArray API.
// Inefficient, but easy to write:
void calcMagnitude(vtkDataArray *vectors, vtkDataArray *magnitude)
{
  vtkIdType numVectors = vectors->GetNumberOfTuples();
  for (vtkIdType tupleIdx = 0; tupleIdx < numVectors; ++tupleIdx)
    {
    // What data types are magnitude and vectors using?
    // We don't care! These methods all use double.
    magnitude->SetComponent(tupleIdx, 0,
      std::sqrt(vectors->GetComponent(tupleIdx, 0) *
                vectors->GetComponent(tupleIdx, 0) +
                vectors->GetComponent(tupleIdx, 1) *
                vectors->GetComponent(tupleIdx, 1) +
                vectors->GetComponent(tupleIdx, 2) *
                vectors->GetComponent(tupleIdx, 2));
    }
}
```

### The Costs of Flexibility

However, this flexibility comes at a cost. Passing data through a generic API
has a number of issues:

__Accuracy__

Not all ValueTypes are fully expressible as a `double`. The truncation of
integers with > 52 bits of precision can be a particularly nasty issue.

__Performance__

__Virtual overhead__: The only way to implement such a system is to route the
`vtkDataArray` calls through a run-time resolution of ValueTypes. This is
implemented through the virtual override mechanism of C++, which adds a small
overhead to each API call.

__Missed optimization__: The virtual indirection described above also prevents
the compiler from being able to make assumptions about the layout of the data
in-memory. This information could be used to perform advanced optimizations,
such as vectorization.

So what can one do if they want fast, optimized, type-safe access to the data
stored in a `vtkDataArray`? What options are available?

### The Old Solution: vtkTemplateMacro

The `vtkTemplateMacro` is described in this section. While it is no longer
considered a best practice to use this construct in new code, it is still
usable and likely to be encountered when reading the VTK source code. Newer
code should use the `vtkArrayDispatch` mechanism, which is detailed later. The
discussion of `vtkTemplateMacro` will help illustrate some of the practical
issues with array dispatching.

With a few minor exceptions that we won't consider here, prior to VTK 7.1 it
was safe to assume that all numeric `vtkDataArray` objects were also subclasses
of `vtkDataArrayTemplate`. This template class provided the implementation of
all documented numeric data arrays such as `vtkDoubleArray`, `vtkIdTypeArray`,
etc, and stores the tuples in memory as a contiguous array-of-structs (AOS).
For example, if we had an array that stored 3-component tuples as floating
point numbers, we could define a tuple as:

```cpp
struct Tuple { float x; float y; float z; };
```

An array-of-structs, or AOS, memory buffer containing this data could be
described as:

```cpp
Tuple ArrayOfStructsBuffer[NumTuples];
```

As a result, `ArrayOfStructsBuffer` will have the following memory layout:

```cpp
{ x1, y1, z1, x2, y2, z2, x3, y3, z3, ...}
```

That is, the components of each tuple are stored in adjacent memory locations,
one tuple after another. While this is not exactly how `vtkDataArrayTemplate`
implemented its memory buffers, it accurately describes the resulting memory
layout.

`vtkDataArray` also defines a `GetDataType` method, which returns an enumerated
value describing a type. We can used to discover the ValueType stored in the
array.

Combine the AOS memory convention and `GetDataType()` with a horrific little
method on the data arrays named `GetVoidPointer()`, and a path to efficient,
type-safe access was available. `GetVoidPointer()` does what it says on the
tin: it returns the memory address for the array data's base location as a
`void*`. While this breaks encapsulation and sets off warning bells for the
more pedantic among us, the following technique was safe and efficient when
used correctly:

```cpp
// 3-component magnitude calculation using GetVoidPointer.
// Efficient and fast, but assumes AOS memory layout
template <typename ValueType>
void calcMagnitudeWorker(ValueType *vectors, ValueType *magnitude,
                         vtkIdType numVectors)
{
  for (vtkIdType tupleIdx = 0; tupleIdx < numVectors; ++tupleIdx)
    {
    // We now have access to the raw memory buffers, and assuming
    // AOS memory layout, we know how to access them.
    magnitude[tupleIdx] =
      std::sqrt(vectors[3 * tupleIdx + 0] *
                vectors[3 * tupleIdx + 0] +
                vectors[3 * tupleIdx + 1] *
                vectors[3 * tupleIdx + 1] +
                vectors[3 * tupleIdx + 2] *
                vectors[3 * tupleIdx + 2]);
    }
}

void calcMagnitude(vtkDataArray *vectors, vtkDataArray *magnitude)
{
  assert("Arrays must have same datatype!" &&
         vtkDataTypesCompare(vectors->GetDataType(),
                             magnitude->GetDataType()));
  switch (vectors->GetDataType())
    {
    vtkTemplateMacro(calcMagnitudeWorker<VTK_TT*>(
      static_cast<VTK_TT*>(vectors->GetVoidPointer(0)),
      static_cast<VTK_TT*>(magnitude->GetVoidPointer(0)),
      vectors->GetNumberOfTuples());
    }
}
```

The `vtkTemplateMacro`, as you may have guessed, expands into a series of case
statements that determine an array's ValueType from the `int GetDataType()`
return value. The ValueType is then `typedef`'d to `VTK_TT`, and the macro's
argument is called for each numeric type returned from `GetDataType`. In this
case, the call to `calcMagnitudeWorker` is made by the macro, with `VTK_TT`
`typedef`'d to the array's ValueType.

This is the typical usage pattern for `vtkTemplateMacro`. The `calcMagnitude`
function calls a templated worker implementation that uses efficient, raw
memory access to a typesafe memory buffer so that the worker's code can be as
efficient as possible. But this assumes AOS memory ordering, and as we'll
mention, this assumption may no longer be valid as VTK moves further into the
field of in-situ analysis.

But first, you may have noticed that the above example using `vtkTemplateMacro`
has introduced a step backwards in terms of functionality. In the
`vtkDataArray` implementation, we didn't care if both arrays were the same
ValueType, but now we have to ensure this, since we cast both arrays' `void`
pointers to `VTK_TT`*. What if vectors is an array of integers, but we want to
calculate floating point magnitudes?

### vtkTemplateMacro with Multiple Arrays

The best solution prior to VTK 7.1 was to use two worker functions. The first
is templated on vector's ValueType, and the second is templated on both array
ValueTypes:

```cpp
// 3-component magnitude calculation using GetVoidPointer and a
// double-dispatch to resolve ValueTypes of both arrays.
// Efficient and fast, but assumes AOS memory layout, lots of boilerplate
// code, and the sensitivity to template explosion issues increases.
template <typename VectorType, typename MagnitudeType>
void calcMagnitudeWorker2(VectorType *vectors, MagnitudeType *magnitude,
                          vtkIdType numVectors)
{
  for (vtkIdType tupleIdx = 0; tupleIdx < numVectors; ++tupleIdx)
    {
    // We now have access to the raw memory buffers, and assuming
    // AOS memory layout, we know how to access them.
    magnitude[tupleIdx] =
      std::sqrt(vectors[3 * tupleIdx + 0] *
                vectors[3 * tupleIdx + 0] +
                vectors[3 * tupleIdx + 1] *
                vectors[3 * tupleIdx + 1] +
                vectors[3 * tupleIdx + 2] *
                vectors[3 * tupleIdx + 2]);
    }
}

// Vector ValueType is known (VectorType), now use vtkTemplateMacro on
// magnitude:
template <typename VectorType>
void calcMagnitudeWorker1(VectorType *vectors, vtkDataArray *magnitude,
                          vtkIdType numVectors)
{
  switch (magnitude->GetDataType())
    {
    vtkTemplateMacro(calcMagnitudeWorker2(vectors,
      static_cast<VTK_TT*>(magnitude->GetVoidPointer(0)), numVectors);
    }
}

void calcMagnitude(vtkDataArray *vectors, vtkDataArray *magnitude)
{
  // Dispatch vectors first:
  switch (vectors->GetDataType())
    {
    vtkTemplateMacro(calcMagnitudeWorker1<VTK_TT*>(
      static_cast<VTK_TT*>(vectors->GetVoidPointer(0)),
      magnitude, vectors->GetNumberOfTuples());
    }
}
```

This works well, but it's a bit ugly and has the same issue as before regarding
memory layout. Double dispatches using this method will also see more problems
regarding binary size. The number of template instantiations that the compiler
needs to generate is determined by `I = T^D`, where `I` is the number of
template instantiations, `T` is the number of types considered, and `D` is the
number of dispatches. As of VTK 7.1, `vtkTemplateMacro` considers 14 data
types, so this double-dispatch will produce 14 instantiations of
`calcMagnitudeWorker1` and 196 instantiations of `calcMagnitudeWorker2`. If we
tried to resolve 3 `vtkDataArray`s into raw C arrays, 2744 instantiations of
the final worker function would be generated. As more arrays are considered,
the need for some form of restricted dispatch becomes very important to keep
this template explosion in check.

### Data Array Changes in VTK 7.1

Starting with VTK 7.1, the Array-Of-Structs (AOS) memory layout is no longer
the only `vtkDataArray` implementation provided by the library. The
Struct-Of-Arrays (SOA) memory layout is now available through the
`vtkSOADataArrayTemplate` class. The SOA layout assumes that the components of
an array are stored separately, as in:

```cpp
struct StructOfArraysBuffer
{
  float *x; // Pointer to array containing x components
  float *y; // Same for y
  float *z; // Same for z
};
```

The new SOA arrays were added to improve interoperability between VTK and
simulation packages for live visualization of in-situ results. Many simulations
use the SOA layout for their data, and natively supporting these arrays in VTK
will allow analysis of live data without the need to explicitly copy it into a
VTK data structure.

As a result of this change, a new mechanism is needed to efficiently access
array data. `vtkTemplateMacro` and `GetVoidPointer` are no longer an acceptable
solution -- implementing `GetVoidPointer` for SOA arrays requires creating a
deep copy of the data into a new AOS buffer, a waste of both processor time and
memory.

So we need a replacement for `vtkTemplateMacro` that can abstract away things
like storage details while providing performance that is on-par with raw memory
buffer operations. And while we're at it, let's look at removing the tedium of
multi-array dispatch and reducing the problem of 'template explosion'. The
remainder of this page details such a system.

## Best Practices for vtkDataArray Post-7.1

We'll describe a new set of tools that make managing template instantiations
for efficient array access both easy and extensible. As an overview, the
following new features will be discussed:

* `vtkGenericDataArray`: The new templated base interface for all numeric
`vtkDataArray` subclasses.
* `vtkArrayDispatch`: Collection of code generation tools that allow concise
and precise specification of restrictable dispatch for up to 3 arrays
simultaneously.
* `vtkArrayDownCast`: Access to specialized downcast implementations from code
templates.
* `vtkDataArrayAccessor`: Provides `Get` and `Set` methods for
accessing/modifying array data as efficiently as possible. Allows a single
worker implementation to work efficiently with `vtkGenericDataArray`
subclasses, or fallback to use the `vtkDataArray` API if needed.
* `VTK_ASSUME`: New abstraction for the compiler `__assume` directive to
provide optimization hints.

These will be discussed more fully, but as a preview, here's our familiar
`calcMagnitude` example implemented using these new tools:

```cpp
// Modern implementation of calcMagnitude using new concepts in VTK 7.1:
// A worker functor. The calculation is implemented in the function template
// for operator().
struct CalcMagnitudeWorker
{
  // The worker accepts VTK array objects now, not raw memory buffers.
  template <typename VectorArray, typename MagnitudeArray>
  void operator()(VectorArray *vectors, MagnitudeArray *magnitude)
  {
    // This allows the compiler to optimize for the AOS array stride.
    VTK_ASSUME(vectors->GetNumberOfComponents() == 3);
    VTK_ASSUME(magnitude->GetNumberOfComponents() == 1);

    // These allow this single worker function to be used with both
    // the vtkDataArray 'double' API and the more efficient
    // vtkGenericDataArray APIs, depending on the template parameters:
    vtkDataArrayAccessor<VectorArray> v(vectors);
    vtkDataArrayAccessor<MagnitudeArray> m(magnitude);

    vtkIdType numVectors = vectors->GetNumberOfTuples();
    for (vtkIdType tupleIdx = 0; tupleIdx < numVectors; ++tupleIdx)
      {
      // Set and Get compile to inlined optimizable raw memory accesses for
      // vtkGenericDataArray subclasses.
      m.Set(tupleIdx, 0, std::sqrt(v.Get(tupleIdx, 0) * v.Get(tupleIdx, 0) +
                                   v.Get(tupleIdx, 1) * v.Get(tupleIdx, 1) +
                                   v.Get(tupleIdx, 2) * v.Get(tupleIdx, 2)));
      }
  }
};

void calcMagnitude(vtkDataArray *vectors, vtkDataArray *magnitude)
{
  // Create our worker functor:
  CalcMagnitudeWorker worker;

  // Define our dispatcher. We'll let vectors have any ValueType, but only
  // consider float/double arrays for magnitudes. These combinations will
  // use a 'fast-path' implementation generated by the dispatcher:
  typedef vtkArrayDispatch::Dispatch2ByValueType
    <
      vtkArrayDispatch::AllTypes, // ValueTypes allowed by first array
      vtkArrayDispatch::Reals // ValueTypes allowed by second array
    > Dispatcher;

  // Execute the dispatcher:
  if (!Dispatcher::Execute(vectors, magnitude, worker))
    {
    // If Execute() fails, it means the dispatch failed due to an
    // unsupported array type. In this case, it's likely that the magnitude
    // array is using an integral type. This is an uncommon case, so we won't
    // generate a fast path for these, but instead call an instantiation of
    // CalcMagnitudeWorker::operator()<vtkDataArray, vtkDataArray>.
    // Through the use of vtkDataArrayAccessor, this falls back to using the
    // vtkDataArray double API:
    worker(vectors, magnitude);
    }
}
```

## vtkGenericDataArray

The `vtkGenericDataArray` class template drives the new `vtkDataArray` class
hierarchy. The ValueType is introduced here, both as a template parameter and a
class-scope `typedef`. This allows a typed API to be written that doesn't
require conversion to/from a common type (as `vtkDataArray` does with double).
It does not implement any storage details, however. Instead, it uses the CRTP
idiom to forward key method calls to a derived class without using a virtual
function call. By eliminating this indirection, `vtkGenericDataArray` defines
an interface that can be used to implement highly efficient code, because the
compiler is able to see past the method calls and optimize the underlying
memory accesses instead.

There are two main subclasses of `vtkGenericDataArray`:
`vtkAOSDataArrayTemplate` and `vtkSOADataArrayTemplate`. These implement
array-of-structs and struct-of-arrays storage, respectively.

## vtkTypeList

Type lists are a metaprogramming construct used to generate a list of C++
types. They are used in VTK to implement restricted array dispatching. As we'll
see, `vtkArrayDispatch` offers ways to reduce the number of generated template
instantiations by enforcing constraints on the arrays used to dispatch. For
instance, if one wanted to only generate templated worker implementations for
`vtkFloatArray` and `vtkIntArray`, a typelist is used to specify this:

```cpp
// Create a typelist of 2 types, vtkFloatArray and vtkIntArray:
typedef vtkTypeList::Create<vtkFloatArray, vtkIntArray> MyArrays;

Worker someWorker = ...;
vtkDataArray *someArray = ...;

// Use vtkArrayDispatch to generate code paths for these arrays:
vtkArrayDispatch::DispatchByArray<MyArrays>(someArray, someWorker);
```

There's not much to know about type lists as a user, other than how to create
them. As seen above, there is a set of macros named `vtkTypeList::Create<...>`,
where X is the number of types in the created list, and the arguments are the
types to place in the list. In the example above, the new type list is
typically bound to a friendlier name using a local `typedef`, which is a common
practice.

The `vtkTypeList.h` header defines some additional type list operations that
may be useful, such as deleting and appending types, looking up indices, etc.
`vtkArrayDispatch::FilterArraysByValueType` may come in handy, too. But for
working with array dispatches, most users will only need to create new ones, or
use one of the following predefined `vtkTypeLists`:

* `vtkArrayDispatch::Reals`: All floating point ValueTypes.
* `vtkArrayDispatch::Integrals`: All integral ValueTypes.
* `vtkArrayDispatch::AllTypes`: Union of Reals and Integrals.
* `vtkArrayDispatch::Arrays`: Default list of ArrayTypes to use in dispatches.

The last one is special -- `vtkArrayDispatch::Arrays` is a typelist of
ArrayTypes set application-wide when VTK is built. This `vtkTypeList` of
`vtkDataArray` subclasses is used for unrestricted dispatches, and is the list
that gets filtered when restricting a dispatch to specific ValueTypes.

Refining this list allows the user building VTK to have some control over the
dispatch process. If SOA arrays are never going to be used, they can be removed
from dispatch calls, reducing compile times and binary size. On the other hand,
a user applying in-situ techniques may want them available, because they'll be
used to import views of intermediate results.

By default, `vtkArrayDispatch::Arrays` contains all AOS arrays. The `CMake`
option `VTK_DISPATCH_SOA_ARRAYS` will enable SOA array dispatch as well. More
advanced possibilities exist and are described in
`VTK/Common/Core/vtkCreateArrayDispatchArrayList.cmake`.

## vtkArrayDownCast

In VTK, all subclasses of `vtkObject` (including the data arrays) support a
downcast method called `SafeDownCast`. It is used similarly to the C++
`dynamic_cast` -- given an object, try to cast it to a more derived type or
return `NULL` if the object is not the requested type. Say we have a
`vtkDataArray` and want to test if it is actually a `vtkFloatArray`. We can do
this:

```cpp
void DoSomeAction(vtkDataArray *dataArray)
{
  vtkFloatArray *floatArray = vtkFloatArray::SafeDownCast(dataArray);
  if (floatArray)
    {
    // ... (do work with float array)
    }
}
```

This works, but it can pose a serious problem if `DoSomeAction` is called
repeatedly. `SafeDownCast` works by performing a series of virtual calls and
string comparisons to determine if an object falls into a particular class
hierarchy. These string comparisons add up and can actually dominate
computational resources if an algorithm implementation calls `SafeDownCast` in
a tight loop.

In such situations, it's ideal to restructure the algorithm so that the
downcast only happens once and the same result is used repeatedly, but
sometimes this is not possible. To lessen the cost of downcasting arrays, a
`FastDownCast` method exists for common subclasses of `vtkAbstractArray`. This
replaces the string comparisons with a single virtual call and a few integer
comparisons and is far cheaper than the more general SafeDownCast. However, not
all array implementations support the `FastDownCast` method.

This creates a headache for templated code. Take the following example:

```cpp
template <typename ArrayType>
void DoSomeAction(vtkAbstractArray *array)
{
  ArrayType *myArray = ArrayType::SafeDownCast(array);
  if (myArray)
    {
    // ... (do work with myArray)
    }
}
```

We cannot use `FastDownCast` here since not all possible ArrayTypes support it.
But we really want that performance increase for the ones that do --
`SafeDownCast`s are really slow! `vtkArrayDownCast` fixes this issue:

```cpp
template <typename ArrayType>
void DoSomeAction(vtkAbstractArray *array)
{
  ArrayType *myArray = vtkArrayDownCast<ArrayType>(array);
  if (myArray)
    {
    // ... (do work with myArray)
    }
}
```

`vtkArrayDownCast` automatically selects `FastDownCast` when it is defined for
the ArrayType, and otherwise falls back to `SafeDownCast`. This is the
preferred array downcast method for performance, uniformity, and reliability.

## vtkDataArrayAccessor

Array dispatching relies on having templated worker code carry out some
operation. For instance, take this `vtkArrayDispatch` code that locates the
maximum value in an array:

```cpp
// Stores the tuple/component coordinates of the maximum value:
struct FindMax
{
  vtkIdType Tuple; // Result
  int Component; // Result

  FindMax() : Tuple(-1), Component(-1) {}

  template <typename ArrayT>
  void operator()(ArrayT *array)
  {
    // The type to use for temporaries, and a temporary to store
    // the current maximum value:
    typedef typename ArrayT::ValueType ValueType;
    ValueType max = std::numeric_limits<ValueType>::min();

    // Iterate through all tuples and components, noting the location
    // of the largest element found.
    vtkIdType numTuples = array->GetNumberOfTuples();
    int numComps = array->GetNumberOfComponents();
    for (vtkIdType tupleIdx = 0; tupleIdx < numTuples; ++tupleIdx)
      {
      for (int compIdx = 0; compIdx < numComps; ++compIdx)
        {
        if (max < array->GetTypedComponent(tupleIdx, compIdx))
          {
          max = array->GetTypedComponent(tupleIdx, compIdx);
          this->Tuple = tupleIdx;
          this->Component = compIdx;
          }
        }
      }
  }
};

void someFunction(vtkDataArray *array)
{
  FindMax maxWorker;
  vtkArrayDispatch::Dispatch::Execute(array, maxWorker);
  // Do work using maxWorker.Tuple and maxWorker.Component...
}
```

There's a problem, though. Recall that only the arrays in
`vtkArrayDispatch::Arrays` are tested for dispatching. What happens if the
array passed into someFunction wasn't on that list?

The dispatch will fail, and `maxWorker.Tuple` and `maxWorker.Component` will be
left to their initial values of -1. That's no good. What if `someFunction` is a
critical path where we want to use a fast dispatched worker if possible, but
still have valid results to use if dispatching fails? Well, we can fall back on
the `vtkDataArray` API and do things the slow way in that case. When a
dispatcher is given an unsupported array, Execute() returns false, so let's
just add a backup implementation:

```cpp
// Stores the tuple/component coordinates of the maximum value:
struct FindMax
{ /* As before... */ };

void someFunction(vtkDataArray *array)
{
  FindMax maxWorker;
  if (!vtkArrayDispatch::Dispatch::Execute(array, maxWorker))
    {
    // Reimplement FindMax::operator(), but use the vtkDataArray API's
    // "virtual double GetComponent()" instead of the more efficient
    // "ValueType GetTypedComponent()" from vtkGenericDataArray.
    }
}
```

Ok, that works. But ugh...why write the same algorithm twice? That's extra
debugging, extra testing, extra maintenance burden, and just plain not fun.

Enter `vtkDataArrayAccessor`. This utility template does a very simple, yet
useful, job. It provides component and tuple based `Get` and `Set` methods that
will call the corresponding method on the array using either the `vtkDataArray`
or `vtkGenericDataArray` API, depending on the class's template parameter. It
also defines an `APIType`, which can be used to allocate temporaries, etc. This
type is double for `vtkDataArray`s and `vtkGenericDataArray::ValueType` for
`vtkGenericDataArray`s.

Another nice benefit is that `vtkDataArrayAccessor` has a more compact API. The
only defined methods are Get and Set, and they're overloaded to work on either
tuples or components (though component access is encouraged as it is much, much
more efficient). Note that all non-element access operations (such as
`GetNumberOfTuples`) should still be called on the array pointer using
`vtkDataArray` API.

Using `vtkDataArrayAccessor`, we can write a single worker template that works
for both `vtkDataArray` and `vtkGenericDataArray`, without a loss of
performance in the latter case. That worker looks like this:

```cpp
// Better, uses vtkDataArrayAccessor:
struct FindMax
{
  vtkIdType Tuple; // Result
  int Component; // Result

  FindMax() : Tuple(-1), Component(-1) {}

  template <typename ArrayT>
  void operator()(ArrayT *array)
  {
    // Create the accessor:
    vtkDataArrayAccessor<ArrayT> access(array);

    // Prepare the temporary. We'll use the accessor's APIType instead of
    // ArrayT::ValueType, since that is appropriate for the vtkDataArray
    // fallback:
    typedef typename vtkDataArrayAccessor<ArrayT>::APIType ValueType;
    ValueType max = std::numeric_limits<ValueType>::min();

    // Iterate as before, but use access.Get instead of
    // array->GetTypedComponent. GetTypedComponent is still used
    // when ArrayT is a vtkGenericDataArray, but
    // vtkDataArray::GetComponent is now used as a fallback when ArrayT
    // is vtkDataArray.
    vtkIdType numTuples = array->GetNumberOfTuples();
    int numComps = array->GetNumberOfComponents();
    for (vtkIdType tupleIdx = 0; tupleIdx < numTuples; ++tupleIdx)
      {
      for (int compIdx = 0; compIdx < numComps; ++compIdx)
        {
        if (max < access.Get(tupleIdx, compIdx))
          {
          max = access.Get(tupleIdx, compIdx);
          this->Tuple = tupleIdx;
          this->Component = compIdx;
          }
        }
      }
  }
};
```

Now when we call `operator()` with say, `ArrayT=vtkFloatArray`, we'll get an
optimized, efficient code path. But we can also call this same implementation
with `ArrayT=vtkDataArray` and still get a correct result (assuming that the
`vtkDataArray`'s double API represents the data well enough).

Using the `vtkDataArray` fallback path is straightforward. At the call site:

```cpp
void someFunction(vtkDataArray *array)
{
  FindMax maxWorker;
  if (!vtkArrayDispatch::Dispatch::Execute(array, maxWorker))
    {
    maxWorker(array); // Dispatch failed, call vtkDataArray fallback
    }
  // Do work using maxWorker.Tuple and maxWorker.Component -- now we know
  // for sure that they're initialized!
}
```

Using the above pattern for calling a worker and always going through
`vtkDataArrayAccessor` to `Get`/`Set` array elements ensures that any worker
implementation can be its own fallback path.

## VTK_ASSUME

While performance testing the new array classes, we compared the performance of
a dispatched worker using the `vtkDataArrayAccessor` class to the same
algorithm using raw memory buffers. We managed to achieve the same performance
out of the box for most cases, using both AOS and SOA array implementations. In
fact, with `--ffast-math` optimizations on GCC 4.9, the optimizer is able to
remove all function calls and apply SIMD vectorized instructions in the
dispatched worker, showing that the new array API is thin enough that the
compiler can see the algorithm in terms of memory access.

But there was one case where performance suffered. If iterating through an AOS
data array with a known number of components using `GetTypedComponent`, the raw
pointer implementation initially outperformed the dispatched array. To
understand why, note that the AOS implementation of `GetTypedComponent` is along
the lines of:

```cpp
ValueType vtkAOSDataArrayTemplate::GetTypedComponent(vtkIdType tuple,
                                                     int comp) const
{
  // AOSData is a ValueType* pointing at the base of the array data.
  return this->AOSData[tuple * this->NumberOfComponents + comp];
}
```

Because `NumberOfComponents` is unknown at compile time, the optimizer cannot
assume anything about the stride of the components in the array. This leads to
missed optimizations for vectorized read/writes and increased complexity in the
instructions used to iterate through the data.

For such cases where the number of components is, in fact, known at compile
time (due to a calling function performing some validation, for instance), it
is possible to tell the compiler about this fact using `VTK_ASSUME`.

`VTK_ASSUME` wraps a compiler-specific `__assume` statement, which is used to
pass such optimization hints. Its argument is an expression of some condition
that is guaranteed to always be true. This allows more aggressive optimizations
when used correctly, but be forewarned that if the condition is not met at
runtime, the results are unpredictable and likely catastrophic.

But if we're writing a filter that only operates on 3D point sets, we know the
number of components in the point array will always be 3. In this case we can
write:

```cpp
VTK_ASSUME(pointsArray->GetNumberOfComponents() == 3);
```

in the worker function and this instructs the compiler that the array's
internal `NumberOfComponents` variable will always be 3, and thus the stride of
the array is known. Of course, the caller of this worker function should ensure
that this is a 3-component array and fail gracefully if it is not.

There are many scenarios where `VTK_ASSUME` can offer a serious performance
boost, the case of known tuple size is a common one that's really worth
remembering.

## vtkArrayDispatch

The dispatchers implemented in the vtkArrayDispatch namespace provide array
dispatching with customizable restrictions on code generation and a simple
syntax that hides the messy details of type resolution and multi-array
dispatch. There are several "flavors" of dispatch available that operate on up
to three arrays simultaneously.

### Components Of A Dispatch

Using the `vtkArrayDispatch` system requires three elements: the array(s), the
worker, and the dispatcher.

#### The Arrays

All dispatched arrays must be subclasses of `vtkDataArray`. It is important to
identify as many restrictions as possible. Must every ArrayType be considered
during dispatch, or is the array's ValueType (or even the ArrayType itself)
restricted? If dispatching multiple arrays at once, are they expected to have
the same ValueType? These scenarios are common, and these conditions can be
used to reduce the number of instantiations of the worker template.

#### The Worker

The worker is some generic callable. In C++98, a templated functor is a good
choice. In C++14, a generic lambda is a usable option as well. For our
purposes, we'll only consider the functor approach, as C++14 is a long ways off
for core VTK code.

At a minimum, the worker functor should define `operator()` to make it
callable. This should be a function template with a template parameter for each
array it should handle. For a three array dispatch, it should look something
like this:

```cpp
struct ThreeArrayWorker
{
  template <typename Array1T, typename Array2T, typename Array3T>
  void operator()(Array1T *array1, Array2T *array2, Array3T *array3)
  {
  /* Do stuff... */
  }
};
```

At runtime, the dispatcher will call `ThreeWayWorker::operator()` with a set of
`Array1T`, `Array2T`, and `Array3T` that satisfy any dispatch restrictions.

Workers can be stateful, too, as seen in the `FindMax` worker earlier where the
worker simply identified the component and tuple id of the largest value in the
array. The functor stored them for the caller to use in further analysis:

```cpp
// Example of a stateful dispatch functor:
struct FindMax
{
  // Functor state, holds results that are accessible to the caller:
  vtkIdType Tuple;
  int Component;

  // Set initial values:
  FindMax() : Tuple(-1), Component(-1) {}

  // Template method to set Tuple and Component ivars:
  template <typename ArrayT>
  void operator()(ArrayT *array)
  {
    /* Do stuff... */
  }
};
```

#### The Dispatcher

The dispatcher is the workhorse of the system. It is responsible for applying
restrictions, resolving array types, and generating the requested template
instantiations. It has responsibilities both at run-time and compile-time.

During compilation, the dispatcher will identify the valid combinations of
arrays that can be used according to the restrictions. This is done by starting
with a typelist of arrays, either supplied as a template parameter or by
defaulting to `vtkArrayDispatch::Arrays`, and filtering them by ValueType if
needed. For multi-array dispatches, additional restrictions may apply, such as
forcing the second and third arrays to have the same ValueType as the first. It
must then generate the required code for the dispatch -- that is, the templated
worker implementation must be instantiated for each valid combination of
arrays.

At runtime, it tests each of the dispatched arrays to see if they match one of
the generated code paths. Runtime type resolution is carried out using
`vtkArrayDownCast` to get the best performance available for the arrays of
interest. If it finds a match, it calls the worker's `operator()` method with
the properly typed arrays. If no match is found, it returns `false` without
executing the worker.

### Restrictions: Why They Matter

We've made several mentions of using restrictions to reduce the number of
template instantiations during a dispatch operation. You may be wondering if it
really matters so much. Let's consider some numbers.

VTK is configured to use 13 ValueTypes for numeric data. These are the standard
numeric types `float`, `int`, `unsigned char`, etc. By default, VTK will define
`vtkArrayDispatch::Arrays` to use all 13 types with `vtkAOSDataArrayTemplate`
for the standard set of dispatchable arrays. If enabled during compilation, the
SOA data arrays are added to this list for a total of 26 arrays.

Using these 26 arrays in a single, unrestricted dispatch will result in 26
instantiations of the worker template. A double dispatch will generate 676
workers. A triple dispatch with no restrictions creates a whopping 17,576
functions to handle the possible combinations of arrays. That's a _lot_ of
instructions to pack into the final binary object.

Applying some simple restrictions can reduce this immensely. Say we know that
the arrays will only contain `float`s or `double`s. This would reduce the
single dispatch to 4 instantiations, the double dispatch to 16, and the triple
to 64. We've just reduced the generated code size significantly. We could even
apply such a restriction to just create some 'fast-paths' and let the integral
types fallback to using the `vtkDataArray` API by using
`vtkDataArrayAccessor`s. Dispatch restriction is a powerful tool for reducing
the compiled size of a binary object.

Another common restriction is that all arrays in a multi-array dispatch have
the same ValueType, even if that ValueType is not known at compile time. By
specifying this restriction, a double dispatch on all 26 AOS/SOA arrays will
only produce 52 worker instantiations, down from 676. The triple dispatch drops
to 104 instantiations from 17,576.

Always apply restrictions when they are known, especially for multi-array
dispatches. The savings are worth it.

### Types of Dispatchers

Now that we've discussed the components of a dispatch operation, what the
dispatchers do, and the importance of restricting dispatches, let's take a look
at the types of dispatchers available.

---

#### vtkArrayDispatch::Dispatch

This family of dispatchers take no parameters and perform an unrestricted
dispatch over all arrays in `vtkArrayDispatch::Arrays`.

__Variations__:
* `vtkArrayDispatch::Dispatch`: Single dispatch.
* `vtkArrayDispatch::Dispatch2`: Double dispatch.
* `vtkArrayDispatch::Dispatch3`: Triple dispatch.

__Arrays considered__: All arrays in `vtkArrayDispatch::Arrays`.

__Restrictions__: None.

__Usecase__: Used when no useful information exists that can be used to apply
restrictions.

__Example Usage__:

```cpp
vtkArrayDispatch::Dispatch::Execute(array, worker);
```

---

#### vtkArrayDispatch::DispatchByArray

This family of dispatchers takes a `vtkTypeList` of explicit array types to use
during dispatching. They should only be used when an array's exact type is
restricted. If dispatching multiple arrays and only one has such type
restrictions, use `vtkArrayDispatch::Arrays` (or a filtered version) for the
unrestricted arrays.

__Variations__:
* `vtkArrayDispatch::DispatchByArray`: Single dispatch.
* `vtkArrayDispatch::Dispatch2ByArray`: Double dispatch.
* `vtkArrayDispatch::Dispatch3ByArray`: Triple dispatch.

__Arrays considered__: All arrays explicitly listed in the parameter lists.

__Restrictions__: Array must be explicitly listed in the dispatcher's type.

__Usecase__: Used when one or more arrays have known implementations.

__Example Usage__:

An example here would be a filter that processes an input array of some
integral type and produces either a `vtkDoubleArray` or a `vtkFloatArray`,
depending on some condition. Since the input array's implementation is unknown
(it comes from outside the filter), we'll rely on a ValueType-filtered version
of `vtkArrayDispatch::Arrays` for its type. However, we know the output array
is either `vtkDoubleArray` or `vtkFloatArray`, so we'll want to be sure to
apply that restriction:

```cpp
// input has an unknown implementation, but an integral ValueType.
vtkDataArray *input = ...;

// Output is always either vtkFloatArray or vtkDoubleArray:
vtkDataArray *output = someCondition ? vtkFloatArray::New()
                                     : vtkDoubleArray::New();

// Define the valid ArrayTypes for input by filtering
// vtkArrayDispatch::Arrays to remove non-integral types:
typedef typename vtkArrayDispatch::FilterArraysByValueType
  <
  vtkArrayDispatch::Arrays,
  vtkArrayDispatch::Integrals
  >::Result InputTypes;

// For output, create a new vtkTypeList with the only two possibilities:
typedef vtkTypeList::Create<vtkFloatArray, vtkDoubleArray> OutputTypes;

// Typedef the dispatch to a more manageable name:
typedef vtkArrayDispatch::Dispatch2ByArray
  <
  InputTypes,
  OutputTypes
  > MyDispatch;

// Execute the dispatch:
MyDispatch::Execute(input, output, someWorker);
```

---

#### vtkArrayDispatch::DispatchByValueType

This family of dispatchers takes a vtkTypeList of ValueTypes for each array and
restricts dispatch to only arrays in vtkArrayDispatch::Arrays that have one of
the specified value types.

__Variations__:
* `vtkArrayDispatch::DispatchByValueType`: Single dispatch.
* `vtkArrayDispatch::Dispatch2ByValueType`: Double dispatch.
* `vtkArrayDispatch::Dispatch3ByValueType`: Triple dispatch.

__Arrays considered__: All arrays in `vtkArrayDispatch::Arrays` that meet the
ValueType requirements.

__Restrictions__: Arrays that do not satisfy the ValueType requirements are
eliminated.

__Usecase__: Used when one or more of the dispatched arrays has an unknown
implementation, but a known (or restricted) ValueType.

__Example Usage__:

Here we'll consider a filter that processes three arrays. The first is a
complete unknown. The second is known to hold `unsigned char`, but we don't
know the implementation. The third holds either `double`s or `float`s, but its
implementation is also unknown.

```cpp
// Complete unknown:
vtkDataArray *array1 = ...;
// Some array holding unsigned chars:
vtkDataArray *array2 = ...;
// Some array holding either floats or doubles:
vtkDataArray *array3 = ...;

// Typedef the dispatch to a more manageable name:
typedef vtkArrayDispatch::Dispatch3ByValueType
  <
  vtkArrayDispatch::AllTypes,
  vtkTypeList::Create<unsigned char>,
  vtkArrayDispatch::Reals
  > MyDispatch;

// Execute the dispatch:
MyDispatch::Execute(array1, array2, array3, someWorker);
```

---

#### vtkArrayDispatch::DispatchByArrayWithSameValueType

This family of dispatchers takes a `vtkTypeList` of ArrayTypes for each array
and restricts dispatch to only consider arrays from those typelists, with the
added requirement that all dispatched arrays share a ValueType.

__Variations__:
* `vtkArrayDispatch::Dispatch2ByArrayWithSameValueType`: Double dispatch.
* `vtkArrayDispatch::Dispatch3ByArrayWithSameValueType`: Triple dispatch.

__Arrays considered__: All arrays in the explicit typelists that meet the
ValueType requirements.

__Restrictions__: Combinations of arrays with differing ValueTypes are
eliminated.

__Usecase__: When one or more arrays are known to belong to a restricted set of
ArrayTypes, and all arrays are known to share the same ValueType, regardless of
implementation.

__Example Usage__:

Let's consider a double array dispatch, with `array1` known to be one of four
common array types (AOS `float`, `double`, `int`, and `vtkIdType` arrays), and
the other is a complete unknown, although we know that it holds the same
ValueType as `array1`.

```cpp
// AOS float, double, int, or vtkIdType array:
vtkDataArray *array1 = ...;
// Unknown implementation, but the ValueType matches array1:
vtkDataArray *array2 = ...;

// array1's possible types:
typedef vtkTypeList;:Create<vtkFloatArray, vtkDoubleArray,
                            vtkIntArray, vtkIdTypeArray> Array1Types;

// array2's possible types:
typedef typename vtkArrayDispatch::FilterArraysByValueType
  <
  vtkArrayDispatch::Arrays,
  vtkTypeList::Create<float, double, int, vtkIdType>
  > Array2Types;

// Typedef the dispatch to a more manageable name:
typedef vtkArrayDispatch::Dispatch2ByArrayWithSameValueType
  <
  Array1Types,
  Array2Types
  > MyDispatch;

// Execute the dispatch:
MyDispatch::Execute(array1, array2, someWorker);
```

---

#### vtkArrayDispatch::DispatchBySameValueType

This family of dispatchers takes a single `vtkTypeList` of ValueType and
restricts dispatch to only consider arrays from `vtkArrayDispatch::Arrays` with
those ValueTypes, with the added requirement that all dispatched arrays share a
ValueType.

__Variations__:
* `vtkArrayDispatch::Dispatch2BySameValueType`: Double dispatch.
* `vtkArrayDispatch::Dispatch3BySameValueType`: Triple dispatch.
* `vtkArrayDispatch::Dispatch2SameValueType`: Double dispatch using
`vtkArrayDispatch::AllTypes`.
* `vtkArrayDispatch::Dispatch3SameValueType`: Triple dispatch using
`vtkArrayDispatch::AllTypes`.

__Arrays considered__: All arrays in `vtkArrayDispatch::Arrays` that meet the
ValueType requirements.

__Restrictions__: Combinations of arrays with differing ValueTypes are
eliminated.

__Usecase__: When one or more arrays are known to belong to a restricted set of
ValueTypes, and all arrays are known to share the same ValueType, regardless of
implementation.

__Example Usage__:

Let's consider a double array dispatch, with `array1` known to be one of four
common ValueTypes (`float`, `double`, `int`, and `vtkIdType` arrays), and
`array2` known to have the same ValueType as `array1`.

```cpp
// Some float, double, int, or vtkIdType array:
vtkDataArray *array1 = ...;
// Unknown, but the ValueType matches array1:
vtkDataArray *array2 = ...;

// The allowed ValueTypes:
typedef vtkTypeList::Create<float, double, int, vtkIdType> ValidValueTypes;

// Typedef the dispatch to a more manageable name:
typedef vtkArrayDispatch::Dispatch2BySameValueType
  <
  ValidValueTypes
  > MyDispatch;

// Execute the dispatch:
MyDispatch::Execute(array1, array2, someWorker);
```

---

## Advanced Usage

### Accessing Memory Buffers

Despite the thin `vtkGenericDataArray` API's nice feature that compilers can
optimize memory accesses, sometimes there are still legitimate reasons to
access the underlying memory buffer. This can still be done safely by providing
overloads to your worker's `operator()` method. For instance,
`vtkDataArray::DeepCopy` uses a generic implementation when mixed array
implementations are used, but has optimized overloads for copying between
arrays with the same ValueType and implementation. The worker for this dispatch
is shown below as an example:

```cpp
// Copy tuples from src to dest:
struct DeepCopyWorker
{
  // AoS --> AoS same-type specialization:
  template <typename ValueType>
  void operator()(vtkAOSDataArrayTemplate<ValueType> *src,
                  vtkAOSDataArrayTemplate<ValueType> *dst)
  {
    std::copy(src->Begin(), src->End(), dst->Begin());
  }

  // SoA --> SoA same-type specialization:
  template <typename ValueType>
  void operator()(vtkSOADataArrayTemplate<ValueType> *src,
                  vtkSOADataArrayTemplate<ValueType> *dst)
  {
    vtkIdType numTuples = src->GetNumberOfTuples();
    for (int comp; comp < src->GetNumberOfComponents(); ++comp)
      {
      ValueType *srcBegin = src->GetComponentArrayPointer(comp);
      ValueType *srcEnd = srcBegin + numTuples;
      ValueType *dstBegin = dst->GetComponentArrayPointer(comp);

      std::copy(srcBegin, srcEnd, dstBegin);
      }
  }

  // Generic implementation:
  template <typename Array1T, typename Array2T>
  void operator()(Array1T *src, Array2T *dst)
  {
    vtkDataArrayAccessor<Array1T> s(src);
    vtkDataArrayAccessor<Array2T> d(dst);

    typedef typename vtkDataArrayAccessor<Array2T>::APIType DestType;

    vtkIdType tuples = src->GetNumberOfTuples();
    int comps = src->GetNumberOfComponents();

    for (vtkIdType t = 0; t < tuples; ++t)
      {
      for (int c = 0; c < comps; ++c)
        {
        d.Set(t, c, static_cast<DestType>(s.Get(t, c)));
        }
      }
  }
};
```

## Putting It All Together

Now that we've explored the new tools introduced with VTK 7.1 that allow
efficient, implementation agnostic array access, let's take another look at the
`calcMagnitude` example from before and identify the key features of the
implementation:

```cpp
// Modern implementation of calcMagnitude using new concepts in VTK 7.1:
struct CalcMagnitudeWorker
{
  template <typename VectorArray, typename MagnitudeArray>
  void operator()(VectorArray *vectors, MagnitudeArray *magnitude)
  {
    VTK_ASSUME(vectors->GetNumberOfComponents() == 3);
    VTK_ASSUME(magnitude->GetNumberOfComponents() == 1);

    vtkDataArrayAccessor<VectorArray> v(vectors);
    vtkDataArrayAccessor<MagnitudeArray> m(magnitude);

    vtkIdType numVectors = vectors->GetNumberOfTuples();
    for (vtkIdType tupleIdx = 0; tupleIdx < numVectors; ++tupleIdx)
      {
      m.Set(tupleIdx, 0, std::sqrt(v.Get(tupleIdx, 0) * v.Get(tupleIdx, 0) +
                                   v.Get(tupleIdx, 1) * v.Get(tupleIdx, 1) +
                                   v.Get(tupleIdx, 2) * v.Get(tupleIdx, 2)));
      }
  }
};

void calcMagnitude(vtkDataArray *vectors, vtkDataArray *magnitude)
{
  CalcMagnitudeWorker worker;
  typedef vtkArrayDispatch::Dispatch2ByValueType
    <
      vtkArrayDispatch::AllTypes,
      vtkArrayDispatch::Reals
    > Dispatcher;

  if (!Dispatcher::Execute(vectors, magnitude, worker))
    {
    worker(vectors, magnitude); // vtkDataArray fallback
    }
}
```

This implementation:

* Uses dispatch restrictions to reduce the number of instantiated templated
worker functions.
 * Assuming 26 types are in `vtkArrayDispatch::Arrays` (13 AOS + 13 SOA).
 * The first array is unrestricted. All 26 array types are considered.
 * The second array is restricted to `float` or `double` ValueTypes, which
 translates to 4 array types (one each, SOA and AOS).
 * 26 * 4 = 104 possible combinations exist. We've eliminated 26 * 22 = 572
 combinations that an unrestricted double-dispatch would have generated (it
 would create 676 instantiations).
* The calculation is still carried out at `double` precision when the ValueType
restrictions are not met.
 * Just because we don't want those other 572 cases to have special code
 generated doesn't necessarily mean that we wouldn't want them to run.
 * Thanks to `vtkDataArrayAccessor`, we have a fallback implementation that
 reuses our templated worker code.
 * In this case, the dispatch is really just a fast-path implementation for
 floating point output types.
* The performance should be identical to iterating through raw memory buffers.
 * The `vtkGenericDataArray` API is transparent to the compiler. The
 specialized instantiations of `operator()` can be heavily optimized since the
 memory access patterns are known and well-defined.
 * Using `VTK_ASSUME` tells the compiler that the arrays have known strides,
 allowing further compile-time optimizations.

Hopefully this has convinced you that the `vtkArrayDispatch` and related tools
are worth using to create flexible, efficient, typesafe implementations for
your work with VTK. Please direct any questions you may have on the subject to
the [VTK Discourse][] forum.

[VTK Discourse]: https://discourse.vtk.org
