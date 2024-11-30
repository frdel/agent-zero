# Python Wrappers

## Introduction

This document is a reference for using VTK from Python. It is not a tutorial
and provides very little information about VTK itself, but instead describes
in detail the features of the Python wrappers and how using VTK from Python
differs from using VTK from C++.  It assumes that the reader is already
somewhat familiar with both Python and VTK.


## Background

The Python wrappers are automatically generated from the VTK source code,
and for the most part, there is a one-to-one mapping between the VTK classes
and methods that you can use from Python and the ones that you can use from
C++.  More specifically, the wrappers are a package of Python extension modules
that interface directly to the VTK C++ libraries.  When you use VTK through
the wrappers, you are actually executing compiled C++ code, and there is
very little performance difference between VTK/C++ and VTK/Python.


## Installation

VTK for Python can be installed via either conda or pip, where the conda
packages is maintained on conda-forge, while the pip packages are maintained
by the VTK developers themselves.  If you are first getting started, then pip
is probably the most convenient way to install VTK for Python:

    pip install vtk

This will provide a basic installation of VTK that includes all core
functionality, but which will not include some of the specialized VTK
modules that rely on external libraries.  Binary packages for VTK can
also be downloaded directly from https://www.vtk.org/download/.

Instructions for building VTK from source code are given in the file
[Documentation/dev/build.md][vtk-build] within the source repository.

[vtk-build]: https://gitlab.kitware.com/vtk/vtk/-/blob/release/Documentation/dev/build.md


## Importing

VTK is comprised of over one hundred individual modules. Programs can import
just the modules that are needed, in order to reduce load time.

    from vtkmodules.vtkCommonCore import vtkObject
    from vtkmodules.vtkFiltersSources import vtkConeSource, vtkSphereSource
    from vtkmodules.vtkRenderingCore import (
        vtkActor,
        vtkDataSetMapper,
        vtkRenderer,
        vtkRenderWindow
    )
    import vtkmodules.vtkRenderingOpenGL2

When getting started, however, it is hard to know what modules you will need.
So if you are experimenting with VTK in a Python console, or writing a quick
and dirty Python script, it is easiest to simply import everything.  There
is a special module called '`all`' that allows this to be done:

    from vtkmodules.all import *

After importing the VTK classes, you can check to see which module each of the
classes comes from:

    for c in vtkObject, vtkConeSource, vtkRenderWindow:
        print(f"from {c.__module__} import {c.__name__}")

The output is as follows:

    from vtkmodules.vtkCommonCore import vtkObject
    from vtkmodules.vtkFiltersSources import vtkConeSource
    from vtkmodules.vtkRenderingCore import vtkRenderWindow

### Factories and Implementation Modules

In the first 'import' example above, you might be wondering about this line:

    import vtkmodules.vtkRenderingOpenGL2

This import is needed because `vtkRenderingOpenGL2` provides the OpenGL
implementations of the classes in `vtkRenderingCore`.  To see this in action,
open a new Python console and do the following:

    >>> from vtkmodules.vtkRenderingCore import vtkRenderWindow
    >>> renwin = vtkRenderWindow()
    >>> type(renwin)
    <class 'vtkmodules.vtkRenderingCore.vtkRenderWindow'>
    >>>
    >>> import vtkmodules.vtkRenderingOpenGL2
    >>> renwin2 = vtkRenderWindow()
    >>> type(renwin2)
    <class 'vtkmodules.vtkRenderingOpenGL2.vtkXOpenGLRenderWindow'>

After `vtkRenderingOpenGL2` has been imported, the `vtkRenderWindow()`
constructor magically starts returning a different type of object.
This occurs because `vtkRenderWindow` is a *factory* class, which means that
the kind of object it produces can be overridden by an *implementation*
class.  In order for the implementation class to do the override, all that
is necessary is that its module is imported.  To make things even more
confusing, `vtkRenderingOpenGL2` is not the only module that contains
implementations for the factory classes in `vtkRenderingCore`.  The following
modules are often needed, as well:

    import vtkmodules.vtkInteractionStyle
    import vtkmodules.vtkRenderingFreeType

Although you only need implementations for the factory classes that you use,
it can be hard to know which classes are factory classes, or what modules
contain implementations for them.  Also, it can be difficult to even know
what classes you are using, since many VTK classes make use of other VTK
classes.  An example of this is `vtkDataSetMapper`, which internally uses
`vtkPolyDataMapper` to do the rendering.  So even though `vtkDataSetMapper` is
not a factory class, it needs an OpenGL implementation for `vtkPolyDataMapper`.

The simplest approach is to import all the important implementation modules
into your program, even if you are not certain that you need them.
* For `vtkRenderingCore`, `import vtkRenderingOpenGL2, vtkRenderingFreeType, vtkInteractionStyle`
* For `vtkRenderingVolume`, `import vtkRenderingVolumeOpenGL2`
* For `vtkCharts`, `import vtkContextOpenGL2`

### Classic VTK Import

There are many VTK programs that still import the '`vtk`' module, which
has been available since VTK 4.0, rather than using the '`vtkmodules`'
package that was introduced in VTK 8.2:

    import vtk

The advantage (and disadvantage) of this is that it imports everything.  It
requires just one import statement for all of VTK, but it can be slow because
VTK has grown to be very large over the years.

Also note that, between VTK 8.2 and VTK 9.2.5, the use of the `vtk` module
would confuse the auto-completion features of IDEs such as PyCharm.  This
was fixed in VTK 9.2.6.  For 9.2.5 and earlier, the following can be used:

    import vtkmodules.all as vtk

From the programmer's perspective, this is equivalent to '`import vtk`'.

## VTK Classes and Objects

### Classes Derived from vtkObjectBase

In C++, classes derived from `vtkObjectBase` are instantiated by calling
`New()`.  In Python, these classes are instantiated by simply calling the
constructor:

    o = vtkObject()

For factory classes, the returned object's type might be a subtype of the
class.  This occurs because the Python wrappers are actually calling `New()`
for you, which allows the VTK factory overrides to occur:

    >>> a = vtkActor()
    >>> type(a)
    <class 'vtkmodules.vtkRenderingOpenGL2.vtkOpenGLActor'>

When you create a VTK object in Python, you are in fact creating two
objects: a C++ object, and a Python object that holds a pointer to the C++
object.  The `repr()` of the object shows the memory address of the C++
object (in parentheses) and of the Python object (after the '`at`'):

    >>> a = vtkFloatArray()
    >>> a
    <vtkmodules.vtkCommonCore.vtkFloatArray(0x5653a6a6f700) at 0x7f0e7aecf5e0>

If you call `str()` or `print()` on these objects, the wrappers will call the
C++ `PrintSelf()` method.  The printed information can be useful for debugging:

    >>> o = vtkObject()
    >>> print(o)
    vtkObject (0x55858308a210)
      Debug: Off
      Modified Time: 85
      Reference Count: 1
      Registered Events: (none)

### Other Classes (Special Types)

VTK also uses several classes that aren't derived from `vtkObjectBase`.  The
most important of these is `vtkVariant`, which can hold any type of object:

    >>> v1 = vtkVariant('hello')
    >>> v1
    vtkmodules.vtkCommonCore.vtkVariant('hello')
    >>> v2 = vtkVariant(3.14)
    >>> v2
    vtkmodules.vtkCommonCore.vtkVariant(3.14)

The wrapping of these classes is fully automatic, but is done in a slightly
different manner than `vtkObjectBase`-derived classes.  First, these classes
have no `New()` method, and instead the public C++ constructors are wrapped
to create an equivalent Python constructor.  Second, the Python object
contains its own copy of the C++ object, rather than containing just a
pointer to the C++ object.  The vast majority of these classes are lightweight
containers and numerical types.  For example, `vtkQuaterniond`, `vtkRectf`,
`vtkColor4ub`, etc.  Many of them are actually class templates, which are
discussed below.

When you apply `print()` or `str()` to these objects, the `operator<<` of the
underlying C++ object is used to print them.  For `repr()`, the name of the
type name is printed, followed by the `str()` output in prentheses.  The
result looks similar to a constructor, though it might look strange depending
on what `operator<<` produces.

    >> v = vtkVariant()
    >> print(repr(v))
    vtkmodules.vtkCommonCore.vtkVariant((invalid))

### Class Templates

There are several C++ templates in VTK, which can be tricky to use from the
wrappers since the Python language has no real concept of templates.  The
wrappers wrap templates as dictionary-like objects that map the template
parameters to template instantiations:

    >>> vtkSOADataArrayTemplate
    <template vtkCommonCorePython.vtkSOADataArrayTemplate>
    >>> vtkSOADataArrayTemplate.keys()
    ['char', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int',
    'uint', 'int64', 'uint64', 'float32', 'float64']
    >>> c = vtkSOADataArrayTemplate['float64']
    >>> c
    <class 'vtkmodules.vtkCommonCore.vtkSOADataArrayTemplate_IdE'>

The wrappers instantiate the C++ template for a few useful types, as
indicated by the `keys()` of the template.  The Python type name also has a
suffix (the '`IdE`') that indicates the template parameters in a compressed
form according to IA64 C++ ABI name mangling rules, even when VTK is built
with a compiler that does not use the IA64 ABI natively.

Objects are created by first instantiating the template, and then
instantiating the class:

    >>> a = vtkSOADataArrayTemplate['float32']()
    >>> a.SetNumberOfComponents(3)

In the case of multiple template parameters, the syntax can look rather
complicated, but really it isn't all that bad.  For example, constructing
a `vtkTuple<double,4>` in Python looks like this, with the template
args in square brackets and the constructor args in parentheses:

    >>> vtkTuple['float64',4]([1.0, 2.0, 3.0, 4.0])
    vtkmodules.vtkCommonMath.vtkTuple_IdLi4EE([1.0, 2.0, 3.0, 4.0])

The type names are the same as numpy's dtypes: `bool`, `int8`, `uint8`,
`int16`, `uint16`, `int32`, `uint32`, `int64`, `uint64`, `float32`, and
`float64`.  Since `int64` is '`long long`', `int` is used for `long`.  Also
see [Template Keys](#template-keys) in [Advanced Topics](#internals-and-advanced-topics).


## Method Calls

When VTK methods are called from Python, conversion of all parameters from
Python to C++ occurs automatically.  That is, if the C++ method signature
expects an integral type, you can pass a Python `int`, and if C++ expects a
floating-point type, you can pass a Python `float` (or any type that allows
implicit conversion to `float`).

For C++ '`char`' parameters, which are rarely used in VTK, you must pass a
string with a length of 1. For unicode, the code must fit into eight bits
(either ASCII, or within the Latin-1 Supplement block).  A null character
is represented by '\\0', or equivalently `chr(0)`.

A Python `tuple`, `list`, or any other Python sequence can be passed to a VTK
method that requires an array or `std::vector` in C++:

    >>> a = vtkActor()
    >>> p = (100.0, 200.0, 100.0)
    >>> a.SetPosition(p)

If the method is going to modify the array that you pass as a parameter,
then you must pass a Python `list` that has the correct number of slots to
accept the returned values.  If you try this with a `tuple`, you will get a
`TypeError` because `tuple` is immutable.

    >>> z = [0.0, 0.0, 0.0]
    >>> vtkMath.Cross((1,0,0),(0,1,0),z)
    >>> print(z)
    [0.0, 0.0, 1.0]

For multi-dimensional array parameters, you can either use a nested list,
or you can use numpy array with the correct shape.

If the C++ method returns a pointer to an array, then in Python the method
will return a tuple if the wrappers know the size of the array.  In most
cases, the size is hinted in the header file.

    >>> a = vtkActor()
    >>> print(a.GetPosition())
    (0.0, 0.0, 0.0)

Finally, Python `None` is treated the same as C++ `nullptr`, which allows
you to pass null objects and null strings:

    >>> a = vtkActor()
    >>> a.SetMapper(None)
    >>> print(a.GetMapper())
    None

### Wrappable and Unwrappable Methods

A method cannot be used from Python if its C++ parameters or return type
cannot be converted to or from Python by the wrappers, or if the method is
templated.  Common non-convertible types include `std::ostream`, `std::istream`,
and all STL container types except for `std::vector` (see below),
and any non-trivial pointer type or any pointer to an object whose class is
not derived from `vtkObjectBase`.

The wrappable parameter types are:
* `char`, wrapped as a single ASCII character in a Python `str`
* `signed char` and `unsigned char`, wrapped as Python `int`
* `short`, `int`, `long` and `long long`, wrapped as Python `int`
* `unsigned short` to `unsigned long long`, wrapped as Python `int`
* `float` and `double`, wrapped as Python `float`
* `size_t` and `ssize_t`, wrapped as Python `int`
* `std::string`, wrapped as Python `str` via utf-8 encoding/decoding
* typedefs of all the above, for any typedef defined in a VTK header file
* `std::vector<T>` where `T` is one of the above, as Python `tuple` or `list`
* `const T&` where `T` is any of the above, wrapped as described above
* `T[N]` where `T` is a fundamental type, as Python `tuple` or `list`
* `T[N][M]` where `T` is a fundamental type, as nested `tuple` or `list`
* `T*` where `T` is a fundamental type, as `tuple` or `list`
* `vtkObjectBase*` and derived types, as their respective Python type
* `vtkSmartPointer<T>` as the Python vtkObjectBase-derived type `T`
* `std::vector<vtkSmartPointer<T>>` as a sequence of objects of type `T`
* `const std::vector<vtkSmartPointer<T>>` as a sequence of objects of type `T`
* other wrapped classes (like `vtkVariant`), but not pointers to these types
* `char*`, as Python `str` via utf-8 encoding/decoding
* `void*`, as Python buffer (e.g. `bytes` or `bytearray`)
* the parameter list `(void (*f)(void*), void*)` as a Python callable type

References like `int&` and `std::string&` are wrapped via a reference proxy
type as described in the [Pass by Reference](#pass-by-reference) section
below.  Non-const references to `std::vector<T>` and other mutable types
do not use a proxy, but instead require that a mutable Python object is
passed, for example a `list` rather than a `tuple`.

A `void*` parameter can accept a pointer in two different ways: either from
any Python object that supports the Python buffer protocol (this includes
all numpy arrays along with the Python bytes and bytearray types), or from a
string that contains a mangled pointer of the form '`_hhhhhhhhhhhh_p_void`'
where '`hhhhhhhhhhhh`' is the hexadecimal address.  Return-value `void*` will
always be a string containing the mangled pointer.

Also, a `T*` parameter for fundamental type `T` can accept a buffer object,
if and only if it is annotated with the `VTK_ZEROCOPY` hint in the header file.
With this hint, a numpy array of `T` can be passed to a `T*` parameter and
the VTK method will directly access the memory buffer of the array.  Hence the
name 'zerocopy', which indicates no copying is done, and that direct memory
access is used.

The `vtkObject::AddObserver()` method has a special wrapping, as discussed
in the [Observer Callbacks](#observer-callbacks) section below.

### Conversion Constructors

If a wrapped type has constructor that takes one parameter, and if that
constructor is not declared '`explicit`', then the wrappers will automatically
use that constructor for type conversion to the parameter type.  The
wrappers ensure that this conversion occurs in Python in the same manner
that it is expected to occur in C++.

For example, `vtkVariantArray` has a method `InsertNextItem(v:vtkVariant)`,
and `vtkVariant` has a constructor `vtkVariant(x:int)`.  So, you can do this:

    >>> variantArray.InsertNextItem(1)

The wrappers will automatically construct a `vtkVariant` from '`1`', and
will then pass it as a parameter to `InsertNextItem()`.  This is a feature
that most C++ programmers will take for granted, but Python users might
find it surprising.

### Overloaded Methods

If you call a VTK method that is overloaded, the Python wrappers will choose
the overload that best matches the supplied arguments.  This matching takes
into account all allowed implicit conversions, such as int to float or any
conversion constructors that are defined for wrapped objects.

Some overloads will be unavailable (not wrapped) either because they are
unwrappable as per the criteria described above, or because they are shadowed
by another overload that is always preferable.  A simple example of this is
any methods that is overloaded on C++ `float` and `double`.  The Python
`float` type is a perfect match C++ `double`, therefore the `float` overload
is not wrapped.

### Static Methods

A static method can be called without an instance.  For example,

    vtkObject.SetGlobalWarningDisplay(1)

Some VTK classes, like vtkMath, consist solely of static methods.  For others,
like `vtkMatrix4x4`, most of the non-static methods have static overloads.
Within Python, the only way to tell if a VTK method is static (other than
trying it) is to look at its docstring.

### Unbound Methods

When a non-static method is called on the class, rather than on an instance,
it is called an unbound method call.  An unbound method call must provide
'self' as the first argument, where 'self' is an instance of either the class
or a subclass.

    w = vtkRenderWindow()
    vtkWindow.Render(w)

In other words, the wrappers translate Python unbound method calls into
C++ unbound method calls.  These are useful when deriving a Python class
from a wrapped VTK class, since they allow you to call any base class
methods that have been overridden in the subclass.

### Operator Methods

For special classes (the ones not derived from `vtkObjectBase`), some useful
C++ operators are wrapped in python.  The '`[]`' operator is wrapped for
indexing and item assignment, but because it relies on hints to guess which
indices are out-of-bounds, it is only wrapped for `vtkVector` and related
classes.

The comparison operators '`<`' '`<=`' '`==`' '`>=`' '`>`' are wrapped for all
classes that have these operators in C++.  These operators allow sorting
of `vtkVariant` objects with Python.

The '`<<`' operator for printing is wrapped and is used by the python
`print()` and `str()` commands.

### Strings and Bytes

VTK uses both `char*` and `std::string` for strings.  As far as the wrappers
are concerned, these are equivalent except that the former can be `nullptr`
(`None` in Python).  For both, the expected encoding is ASCII or utf-8.

In Python, either `str` or `bytes` can be used to store strings, and both
of these can be passed to VTK methods that require `char*` or `std::string`
(or the legacy `vtkStdString`).  A `str` object is passed to VTK as utf-8,
while a `bytes` object is passed as-is.

When a VTK method returns a string, it is received in Python as a `str` object
if it is valid utf-8, or as a `bytes` object if not.  The caller should check
the type of the returned object (`str`, `bytes`, or perhaps `None`) if there
is any reason to suspect that non-utf-8 text might be present.

### STL Containers

VTK provides conversion between `std::vector` and Python sequences
such as `tuple` and `list`.  If the C++ method returns a vector,
the Python method will return a tuple:

    C++: const std::vector<std::string>& GetPaths()
    C++: std::vector<std::string> GetPaths()
    Python: GetPaths() -> Tuple[str]

If the C++ method accepts a vector, then the Python method can be
passed any sequence with compatible values:

    C++: void SetPaths(const std::vector<std::string>& paths)
    C++: void SetPaths(std::vector<std::string> paths)
    Python: SetPaths(paths: Sequence[str]) -> None

Furthermore, if the C++ method accepts a non-const vector reference,
then the Python method can be passed a mutable sequence (e.g. `list`):

    C++: void GetPaths(std::vector<std::string>& paths)
    Python: GetPaths(paths: MutableSequence[str]) -> None

The value type of the `std::vector<T>` must be `std::string` or a
fundamental numeric type such as `double` or `int` (including
`signed char` and `unsigned char` but excluding `char`).

### Smart pointers

The wrappers will automatically convert between C++ `vtkSmartPointer<T>`
and objects of type `T` (or `None`, if the smart pointer is empty):

    C++: vtkSmartPointer<vtkObject> TakeObject()
    Python: TakeObject() -> vtkObject

In other words, in Python the smart pointer doesn't look any different
from the object it points to.  Under the hood, however, the wrappers
understand that the smart pointer carries a reference to the object and
will take responsibility for deleting that reference.

A C++ method can return a vector of smart pointers, which will be seen in
Python as a tuple of objects:

    C++: std::vector<vtkSmartPointer<vtkObject>> GetObjects()
    Python: GetObject() -> Tuple[vtkObject]

If a C++ method expects `std::vector<vtkSmartPointer<T>>` as a parameter,
the wrappers will automatically construct the vector from any sequence that
is passed from Python.  The objects in the sequence must be of type `T` (or
a subclass of `T`, or `None`).  If not, a `TypeError` will be raised.

### Pass by Reference

Many VTK methods use pass-by-reference to return values back to the caller.
Calling these methods from Python requires special consideration, since
Python's `str`, `tuple`, `int`, and `float` types are immutable.  The wrappers
provide a '`reference`' type, which is a simple container that allows
pass-by-reference.

For example, consider the following C++ method that uses pass-by-reference:

    void GetCellAtId(vtkIdType cellId, vtkIdType& cellSize, vtkIdType const*& cellPoints)

It requires a reference to `vtkIdType` (a Python `int`), and to
`vtkIdType const*` (a tuple of `int`s).  So we can call this method as
follows:

    >>> from vtkmodules.vtkCommonCore import reference
    >>> from vtkmodules.vtkCommonDataModel import vtkCellArray
    >>>
    >>> # Build a cell array
    >>> a = vtkCellArray()
    >>> a.InsertNextCell(3, (1, 3, 0))
    >>>
    >>> # Create the reference objects
    >>> n = reference(0)
    >>> t = reference((0,))
    >>>
    >>> # Call the pass-by-reference method
    >>> a.GetCellAtId(0, n, t)
    >>>
    >>> n.get()
    3
    >>> t.get()
    (1, 3, 0)

Some important notes when using pass-by-reference:
1. The reference constructor must be given a value of the desired type.
   The method might use this value or might ignore it.
2. Calling the `get()` method of the reference is usually unnecessary,
   because the reference already supports the interface protocols of the
   object that it contains.

### Preconditions

One very real concern when using VTK from Python is that the parameters that
you pass to a method might cause the program to crash.  In particular, it is
very easy to pass an index that causes an out-of-bounds memory access, since
the C++ methods don't do bounds checking.  As a safety precaution, the
wrappers perform the bounds check before the C++ method is called:

    >>> a = vtkFloatArray()
    >>> a.GetValue(10)
    Traceback (most recent call last):
      File "<stdin>", line 1, in <module>
    ValueError: expects 0 <= id && id < GetNumberOfValues()

All precondition checks raise a `ValueError` if they fail, since they are
checks on the values of the parameters.  The wrappers don't know if C++ is
using the parameter as an index, so `IndexError` is not used.

Currently the only way to find out if a method has preconditions is to look
at the declaration of the method in the C++ header file to see if it has a
`VTK_EXPECTS` hint.

## Observer Callbacks

Similar to what can be done in C++, a Python function can be called
each time a VTK event is invoked on a given object.  In general, the
callback function should have the signature `func(obj:vtkObject, event:str)`,
or `func(self, obj:vtkObject, event:str)` if it is a method of a class.

    >>> def onObjectModified(object, event):
    >>>     print('object: %s - event: %s' % (object.GetClassName(), event))
    >>>
    >>> o = vtkObject()
    >>> o.AddObserver(vtkCommand.ModifiedEvent, onObjectModified)
    1
    >>> o.Modified()
    object: vtkObject - event: ModifiedEvent


### Call Data

In case there is a 'CallData' value associated with an event, in C++, you
have to cast it from `void*` to the expected type using `reinterpret_cast`.
The equivalent in python is to add a `CallDataType` attribute to the
associated python callback method. The supported `CallDataType` values are
`VTK_STRING`, `VTK_OBJECT`, `VTK_INT`, `VTK_LONG`, `VTK_DOUBLE`, and
`VTK_FLOAT`.

The following example uses a function as a callback, but a method or any
callable object can be used:

    >>> from vtkmodules.vtkCommonCore import vtkCommand, VTK_INT
    >>>
    >>> def onError(object, event, calldata):
    >>>     print('object: %s - event: %s - msg: %s' % (object.GetClassName(), event, calldata))
    >>>
    >>> onError.CallDataType = VTK_INT
    >>>
    >>> lt = vtkLookupTable()
    >>> lt.AddObserver(vtkCommand.ErrorEvent, onError)
    1
    >>> lt.SetTableRange(2,1)
    object: vtkLookupTable - event: ErrorEvent - msg: ERROR:
    In /home/user/VTK/Common/Core/vtkLookupTable.cxx, line 122
    vtkLookupTable (0x6b40b30): Bad table range: [2, 1]

For convenience, the `CallDataType` can also be specified where the function
is first declared with the help of the `@calldata_type` decorator:

    >>> from vtkmodules.util.misc import calldata_type
    >>>
    >>> @calldata_type(VTK_INT)
    >>> def onError(object, event, calldata):
    >>>     print('object: %s - event: %s - msg: %s' % (object.GetClassName(),
                                                        event, calldata))

## Other Wrapped Entities

### Constants

Most of the constants defined in the VTK header files are available in Python,
and they can be accessed from the module in which they are defined.  Many of
these are found in the `vtkCommonCore` module, where they were defined as
preprocessor macros.

    >>> from vtkmodules.vtkCommonCore import VTK_DOUBLE_MAX
    >>> VTK_DOUBLE_MAX
    1.0000000000000001e+299

Others are defined as enums, often within a class namespace.  If the enum
is anonymous, then its values are `int`.

    >>> vtkCommand.ErrorEvent
    39

Constants in the header files are wrapped if they are enums, or if they are
const variables of a wrappable scalar type, or if they are preprocessor
symbols that evaluate to integer, floating-point, or string literal types.

### Enum Types

Each named enum type is wrapped as a new Python type, and members of the enum
are instances of that type.  This allows type checking for enum types:

    >>> from vtkmodules.vtkCommonColor import vtkColorSeries
    >>> vtkColorSeries.COOL
    2
    >>> isinstance(vtkColorSeries.ColorSchemes, vtkColorSeries.COOL)
    >>> cs = vtkColorSeries()
    >>> cs.SetColorScheme(vtkColorSeries.COOL)

Enum classes are wrapped in a manner similar to named enums, except that
the enum values are placed within the enum class namespace.  For example,
`vtkEventDataAction` is an enum class, with '`Press`' as a member:

    >>> from vtkmodules.vtkCommonCore import vtkEventDataAction
    >>> vtkEventDataAction.Press
    1
    >>> isinstance(vtkEventDataAction.Press, vtkEventDataAction)
    True

In the first example, the `ColorSchemes` enum type and the `COOL` enum value
were both defined in the `vtkColorSeries` namespace.  In the second example,
the `vtkEventDataAction` enum class was defined in the module namespace,
and the `Press` value was defined in the enum class namespace.

Note that the VTK enum types behave like C++ enums, and not like the Python
enums types provided by the Python '`enum`' module.  In particular, all VTK
enum values can be used anywhere that an `int` can be used.

### Namespaces

Namespaces are currently wrapped in a very limited manner.  The only
namespace members that are wrapped are enum constants and enum types.
There is no wrapping of namespaced classes or functions, or of nested
namespaces.  Currently, the wrappers implement namespaces as Python
`module` objects.


## Docstrings

The wrappers automatically generate docstrings from the doxygen comments in
the header files.  The Python `help()` command can be used to print the
documentation to the screen, or the `__doc__` attributes of the classes
and methods can be accessed directly.

### Method Docstrings

The method docstrings are formatted with the method signatures first,
followed by doxygen comments.  The Python method signatures have type
annotations, and are followed by the C++ method signatures for
completeness.

```
    InvokeEvent(self, event:int, callData:Any) -> int
    C++: int InvokeEvent(unsigned long event, void* callData)
    InvokeEvent(self, event:str, callData:Any) -> int
    C++: int InvokeEvent(const char* event, void* callData)
    InvokeEvent(self, event:int) -> int
    C++: int InvokeEvent(unsigned long event)
    InvokeEvent(self, event:str) -> int
    C++: int InvokeEvent(const char* event)

    This method invokes an event and returns whether the event was
    aborted or not. If the event was aborted, the return value is 1,
    otherwise it is 0.
```

Some Python IDEs will automatically show the docstring as soon as you type
the name of the method.

### Class Docstrings

The class docstrings include a brief description of the class, followed
by the name of the superclass, and then the full doxygen documentation,
including doxygen markup:

```
    vtkMatrix4x4 - represent and manipulate 4x4 transformation matrices

    Superclass: vtkObject

    vtkMatrix4x4 is a class to represent and manipulate 4x4 matrices.
    Specifically, it is designed to work on 4x4 transformation matrices
    found in 3D rendering using homogeneous coordinates [x y z w]. Many
    of the methods take an array of 16 doubles in row-major format. Note
    that OpenGL stores matrices in column-major format, so the matrix
    contents must be transposed when they are moved between OpenGL and
    VTK.
    @sa
    vtkTransform
```

If the class is not derived from `vtkObjectBase`, then it will have one or
more public constructors, and these will be included before the comments:

```
    vtkSimpleCriticalSection() -> vtkSimpleCriticalSection
    C++: vtkSimpleCriticalSection()
    vtkSimpleCriticalSection(isLocked:int) -> vtkSimpleCriticalSection
    C++: vtkSimpleCriticalSection(int isLocked)

    vtkSimpleCriticalSection - Critical section locking class

    vtkCriticalSection allows the locking of variables which are accessed
    through different threads.
```

### Template Docstrings

Class templates are documented similar to classes, except that they include
a 'Provided Types' section that lists the available template instantiations
and the C++ template arguments that they correspond to.

```
    vtkSOADataArrayTemplate - Struct-Of-Arrays implementation of
    vtkGenericDataArray.

    Superclass: vtkGenericDataArray[vtkSOADataArrayTemplate[ValueTypeT],ValueTypeT]

    vtkSOADataArrayTemplate is the counterpart of vtkAOSDataArrayTemplate.
    Each component is stored in a separate array.

    @sa
    vtkGenericDataArray vtkAOSDataArrayTemplate


    Provided Types:

      vtkSOADataArrayTemplate[char] => vtkSOADataArrayTemplate<char>
      vtkSOADataArrayTemplate[int8] => vtkSOADataArrayTemplate<signed char>
      vtkSOADataArrayTemplate[uint8] => vtkSOADataArrayTemplate<unsigned char>
      vtkSOADataArrayTemplate[int16] => vtkSOADataArrayTemplate<short>
      vtkSOADataArrayTemplate[uint16] => vtkSOADataArrayTemplate<unsigned short>
      vtkSOADataArrayTemplate[int32] => vtkSOADataArrayTemplate<int>
      vtkSOADataArrayTemplate[uint32] => vtkSOADataArrayTemplate<unsigned int>
      vtkSOADataArrayTemplate[int] => vtkSOADataArrayTemplate<long>
      vtkSOADataArrayTemplate[uint] => vtkSOADataArrayTemplate<unsigned long>
      vtkSOADataArrayTemplate[int64] => vtkSOADataArrayTemplate<long long>
      vtkSOADataArrayTemplate[uint64] => vtkSOADataArrayTemplate<unsigned long long>
      vtkSOADataArrayTemplate[float32] => vtkSOADataArrayTemplate<float>
      vtkSOADataArrayTemplate[float64] => vtkSOADataArrayTemplate<double>
```

Unlike classes, the template documentation is formatted similarly regardless
of whether the the class template derives from `vtkObjectBase` or not:

```
    vtkVector - templated base type for storage of vectors.

    Superclass: vtkTuple[T,Size]

    This class is a templated data type for storing and manipulating fixed
    size vectors, which can be used to represent two and three dimensional
    points. The memory layout is a contiguous array of the specified type,
    such that a float[2] can be cast to a vtkVector2f and manipulated. Also
    a float[6] could be cast and used as a vtkVector2f[3].


    Provided Types:

      vtkVector[float64,4] => vtkVector<double, 4>
      vtkVector[float32,4] => vtkVector<float, 4>
      vtkVector[int32,4] => vtkVector<int, 4>
      vtkVector[float64,2] => vtkVector<double, 2>
      vtkVector[float32,2] => vtkVector<float, 2>
      vtkVector[int32,2] => vtkVector<int, 2>
      vtkVector[float64,3] => vtkVector<double, 3>
      vtkVector[float32,3] => vtkVector<float, 3>
      vtkVector[int32,3] => vtkVector<int, 3>
```


## Internals and Advanced Topics

### Special Attributes

Classes and objects derived from `vtkObjectBase` have special attributes, which
are only used in very special circumstances.

The `__vtkname__` attribute of the class provides the same string that the
GetClassName() method returns.  With the exception of classes that are
template instantiations, it is identical to the `__name__` attribute.
For template instantiations, however, `GetClassName()` and `__vtkname__`
return the result of calling `typeid(cls).name()` from C++, which provides
a platform specific result:

    >>> vtkSOADataArrayTemplate['float32'].__vtkname__
    '23vtkSOADataArrayTemplateIfE'

This can be used to get the VTK `ClassName` when you don't have an
instantiation to call `GetClassName()` on.  It is useful for checking the
type of a C++ VTK object against a Python VTK class.

The `__this__` attribute of the objects is a bit less esoteric, it provides a
pointer to the C++ object as a mangled string:

    >>> a = vtkFloatArray()
    >>> a.__this__
    '_00005653a6a6f700_p_vtkFloatArray'

The string provides the hexadecimal address of '`this`', followed by '`p`'
(shorthand for *pointer*), and the type of the pointer.  You can also
construct a Python object directly from the C++ address, if the address is
formatted as described above:

    >>> a = vtkFloatArray('_00005653a6a6f700_p_vtkFloatArray')
    >>> a
    <vtkmodules.vtkCommonCore.vtkFloatArray(0x5653a6a6f700) at 0x7f0e7aecf5e0>

If you call the constructor on the string provided by `__this__`, you will
get exactly the same Python object back again, rather than a new object.
But this constructor can be useful if you have some VTK code that has been
wrapped with a different wrapper tool, for example with SWIG.  If you can
get the VTK pointer from SWIG, you can use it to construct Python object
that can be used with the native VTK wrappers.

### Wrapper Hints

A wrapper hint is an attribute that can be added to a class, method, or
parameter declaration in a C++ header file to give extra information to
the wrappers.  These hints are defined in the `vtkWrappingHints.h` header
file.

The following hints can appear before a method declaration:
* `VTK_WRAPEXCLUDE` excludes a method from the wrappers
* `VTK_NEWINSTANCE` passes ownership of a method's return value to the caller

For convenience, `VTK_WRAPEXCLUDE` can also be used to exclude a whole class.
The `VTK_NEWINSTANCE` hint is used when the return value is a `vtkObjectBase*`
and the caller must not increment the reference count upon acceptance of the
object (but must still decrement the reference count when finished with the
object).

The following hints can appear after a method declaration:
* `VTK_EXPECTS(cond)` provides preconditions for the method call
* `VTK_SIZEHINT(expr)` marks the array size of a return value
* `VTK_SIZEHINT(name, expr)` marks the array size of a parameter

For `VTK_EXPECTS(cond)`, the precondition must be valid C++ code, and can
use any of the parameter names or `this`.  Even without `this`, any public
names in the class namespace (including method names) will be resolved.
See the [Preconditions](#preconditions) section for additional information.

`VTK_SIZEHINT(expr)` is used for methods that return an array as type `T*`,
where `T` is a numeric data type.  The hint allows the wrappers to convert the
array to a tuple of the correct size.  Without the size hint, the wrappers
will return the pointer as a string that provides a mangled memory address
of the form '`_hhhhhhhhhhhh_p_void`' where '`hhhhhhhhhhhh`' is address
expressed in hexadecimal.

`VTK_SIZEHINT(parameter_name, expr)` is used to hint parameters of type
`T*` or `T&*` (with `T` as a numeric data type) so that the wrappers know
the size of the array that the pointer is pointing to.  The `expr` can be
any expression that evaluates to an integer, and it can include parameter
names, public class members and method calls, or the special name `_`
(underscore) which indicates the method's return value.  In the absence
of a size hint, the wrappers cannot check that the length of the sequence
passed from Python matches the size of the array required by the method.
If the method requires a larger array than it receives, a buffer overrun
will occur.

The following hints can appear before a parameter declaration:
* `VTK_FILEPATH` marks a parameter that accepts a pathlib.Path object
* `VTK_ZEROCOPY` marks a parameter that accepts a buffer object

More specifically, `VTK_FILEPATH` is used with `char*` and `std::string`
parameters to indicate that the method also accepts any object with a
`__fspath__()` method that returns a path string.  And `VTK_ZEROCOPY` is
used with `T*` parameters, for basic integer or float type `T`, to indicate
that the Python buffer protocol will be used to access the values, rather
than the Python sequence protocol that is used by default.

### Deprecation Warnings

In addition to the wrapping hints, the Python wrappers are also aware of the
deprecation attributes that have been applied to classes and methods.  When
a deprecated method is called, a `DeprecationWarning` is generated and
information about the deprecation is printed, including the VTK version
for the deprecation.

To ignore these warnings, use the following code:

    import warnings
    warnings.filterwarnings('ignore', category=DeprecationWarning)

To see each deprecation warning just once per session,

    warnings.filterwarnings('once', category=DeprecationWarning)

### Template Keys

The following is a table of common template key names, which are the same as
the numpy dtype names.  Note that you can actually use numpy dtypes as keys,
as well as the native Python types `bool`, `int`, and `float`.  There is
some danger in using `int`, however, because it maps to C++ `long` which has
a platform-dependent size (either 32 bits or 64 bits).  Finally, the char
codes from the Python `array` module can be used as keys, but they should
be avoided since more programmers are familiar with numpy than with the
much older `array` module.

| C++ Type           | Template Key | Type Key | Char Key | IA64 ABI Code |
| ------------------ | ------------ | -------- | -------- | ------------- |
| bool               | 'bool'       | bool     | '?'      | IbE           |
| char               | 'char'       |          | 'c'      | IcE           |
| signed char        | 'int8'       |          | 'b'      | IaE           |
| unsigned char      | 'uint8'      |          | 'B'      | IhE           |
| short              | 'int16'      |          | 'h'      | IsE           |
| unsigned short     | 'uint16'     |          | 'H'      | ItE           |
| int                | 'int32'      |          | 'i'      | IiE           |
| unsigned int       | 'uint32'     |          | 'I'      | IjE           |
| long               | 'int'        | int      | 'l'      | IlE           |
| unsigned long      | 'uint'       |          | 'L'      | ImE           |
| long long          | 'int64'      |          | 'q'      | IxE           |
| unsigned long long | 'uint64'     |          | 'Q'      | IyE           |
| float              | 'float32'    |          | 'f'      | IfE           |
| double             | 'float64'    | float    | 'd'      | IdE           |

Since the size of '`long`' and '`unsigned long`' is platform-dependent, these
types should generally be avoided.

### Exception Handling

There are times when an observer might generate a Python exception.  Since
the observers are called from C++, there is no good way to catch these
exceptions from within Python.  So, instead, the wrappers simply print a
traceback to stderr and then clear the error indicator.  The Python program
will continue running unless the exception was a `KeyboardInterrupt` (Ctrl-C),
in which case the program will exit with an error code of 1.

### Deleting a vtkObject

There is no direct equivalent of VTK's `Delete()` method, since Python does
garbage collection automatically.  The Python object will be deleted
when there are no references to it within Python, and the C++ object will
be deleted when there are no references to it from within either Python
or C++. Note that references can hide in unexpected places, for example if
a method of an object is used as an observer callback, the object will not
be deleted until the observer is disconnected.

The `DeleteEvent` can be used to detect object deletion, but note that the
observer will receive a None for the object, since the observer is called
after (not before) the deletion occurs:

    >>> o = vtkObject()
    >>> o.AddObserver('DeleteEvent', lambda o,e: print(e, o))
    1
    >>> del o
    DeleteEvent None

If you need to know what object is deleted, the identifying information must
be extracted before the deletion occurs:

    >>> o = vtkObject()
    >>> o.AddObserver('DeleteEvent',lambda x,e,r=repr(o): print(e, r))
    1
    >>> del o
    DeleteEvent <vtkmodules.vtkCommonCore.vtkObject(0x55783870f970) at 0x7f1e61678be0>

In cases where you need to track down tricky memory issues, you might find
it useful to call the `GetReferenceCount()` method of the object directly.

### Ghosts

A wrapped VTK object (derived from `vtkObjectBase`) is a Python object that
holds a pointer to a C++ object (specifically, a `vtkObjectBase*`).  The
Python object can have attributes that the C++ object knows nothing about.
So, what happens to these attributes if the Python object is deleted, but
the C++ object lives on?  Consider this simple example of storing the C++
object in an array and then deleting the Python object:

    obj = vtkObject()
    obj.tag = 'FirstObject'
    va = vtkVariantArray()
    va.InsertNextValue(obj)
    del obj

When we retrieve the object from the array, we want it to have the '`tag`'
attributes that it had we stored it.  But you might wonder, aren't all
Python-specific attributes deleted along with the Python object?  The
answer is, no they aren't, they're saved until until the C++ object itself
is deleted.

The wrappers have a special place, which we will call the graveyard, where
'ghosts' of objects are stored when the objects are deleted. The ghost is not
an object, but rather a container for the Python attributes of a deceased
object.  If the object ever reappears within Python, usually as a return
value from a C++ method call, then the ghost is resurrected as a new Python
object that has all the attributes of the original Python object.

The graveyard is only used for objects that have unfinished business.  If a
Python object has an empty dict and no other special attributes, then it will
not go to the graveyard.  Also, if the C++ object is deleted at the same time
as the Python object, then the graveyard will not be used.  Each ghost in the
graveyard holds a weak pointer to its C++ object and will vanish when the C++
object is deleted (not immediately, but the next time the graveyard garbage
collector runs).

### Subclassing a VTK Class

It is possible to subclass a VTK class from within Python, but this is of
limited use because the C++ virtual methods are not hooked to the Python
methods.  In other words, if you make a subclass of `vtkPolyDataAlgorithm`
and override override the `Execute()` method, it will not be automatically
called by the VTK pipeline. Your `Execute()` method will only be called if
the call is made from Python.

The addition of virtual method hooks to the wrappers has been proposed,
but currently the only way for Python methods to be called from C++ code
is via callbacks. The `vtkProgrammableSource` and `vtkProgrammableFilter` are
examples of VTK algorithm classes that use callbacks for execution, while
`vtkInteractionStyleUser` can use observer callbacks for event handling.

### Wrapping External VTK Modules

If you have your own C++ classes that are based on VTK, and if they are
placed with a VTK module with a vtk.module file, then they can be wrapped
as shown in the [Module Wrapping Example][external-wrapping].  You will
also find the cmake documentation on VTK modules to be useful.

[external-wrapping]: https://gitlab.kitware.com/vtk/vtk/-/blob/release/Examples/Modules/Wrapping

## Experimental Features

### Python Class Overrides

VTK now supports overriding wrapped classes with Python subclasses.  This
enables developers to provide more Python friendly interfaces for certain
classes.  Here is a trivial example of an override:

    from vtkmodules.vtkCommonCore import vtkPoints
    @vtkPoints.override
    class CustomPoints(vtkPoints):
        pass

Once the override is in place, any future `vtkPoints` Python object instances
will be instances of the override class.  This behavior is global.

    points = vtk.vtkPoints() # returns an instance of CustomPoints

The override can be reversed by setting an override of `None`, but this will
not impact instantiations that have already occurred.

    vtkPoints.override(None)

If the class has already been overridden in C++ via VTK's object factory
mechanism, then directly applying a Python override to that class will not
work.  Instead, the Python override must be applied to the C++ factory
override.  For example, on Windows,

    @vtkWin32OpenGLRenderWindow.override
    class CustomRenderWindow(vtkWin32OpenGLRenderWindow):
        ...
    window = vtkRenderWindow() # creates a CustomRenderWindow

Please see [Subclassing a VTK Class](#subclassing-a-vtk-class) for restrictions on
subclassing VTK classes through Python.


### Stub Files for Type Hinting

VTK includes a script called [`generate_pyi.py`][generate_pyi] that
will generate pyi stub files for each wrapped VTK module.  The purpose of
these files, as explained in [PEP 484][pep_484], is to provide type
information for all constants, classes, and methods in the modules.
Each of these files contain blocks like this:

    VTK_DOUBLE:int
    VTK_DOUBLE_MAX:float
    VTK_DOUBLE_MIN:float
    ...

    class vtkObject(vtkObjectBase):
        def AddObserver(self, event:int, command:Callback, priority:float=0.0) -> int: ...
        def GetMTime(self) -> int: ...
        @staticmethod
        def GetNumberOfGenerationsFromBaseType(type:str) -> int: ...
        @overload
        def HasObserver(self, event:int, __b:'vtkCommand') -> int: ...
        @overload
        def HasObserver(self, event:str, __b:'vtkCommand') -> int: ...

    class vtkAbstractArray(vtkObject):
        class DeleteMethod(int): ...
        VTK_DATA_ARRAY_ALIGNED_FREE:'DeleteMethod'
        VTK_DATA_ARRAY_DELETE:'DeleteMethod'
        VTK_DATA_ARRAY_FREE:'DeleteMethod'
        VTK_DATA_ARRAY_USER_DEFINED:'DeleteMethod'
        def Allocate(self, numValues:int, ext:int=1000) -> int: ...

Python consoles like ipython and IDEs like PyCharm can use the information in
these files to provide hints while you edit the code.  These files are
included in the Python packages for VTK, but they can also be built by
executing the `generate_pyi.py` script.  To do so, execute the script
with the `vtkpython` executable (or with the regular python executable,
if its paths are set for VTK):

    vtkpython -m vtkmodules.generate_pyi

This will place build the pyi files and place them inside the `vtkmodules`
package, where ipython and PyCharm should automatically find them.  The
help for this script is as follows:

    usage: python generate_pyi.py [-p package] [-o output_dir] [module ...]
    options:
      -p NAME        Package name [vtkmodules by default].
      -o OUTPUT      Output directory [package directory by default].
      -e EXT         Output file suffix [.pyi by default].
      module         Module or modules to process [all by default].

The pyi files are syntactically correct python files, so it is possible to
load them as such in order to test them and inspect them.

[generate_pyi]: https://gitlab.kitware.com/vtk/vtk/-/blob/release/Wrapping/Python/vtkmodules/generate_pyi.py
[pep_484]: https://www.python.org/dev/peps/pep-0484/#stub-files
