# Marshalling Hints

## Classes

VTK auto generates (de)serialization code in C++ for classes annotated by
the `VTK_MARSHALAUTO` wrapping hint.

On the other hand, the `VTK_MARSHALMANUAL` macro is used to indicate that a class
will take part in marshalling, but it cannot trivially (de)serialize it's properties.
This is because one or more of the class's properties may not have an appropriate
setter/getter function that is recognized by the VTK property parser.

For such classes, a developer is expected to provide the code to serialize and deserialize the class in `vtkClassNameSerDes.cxx`. This file must satisfy three conditions:

1. It must live in the same module as `vtkClassName`.
2. It must export a function `int RegisterHandlers_vtkClassNameSerDesHelper(void*, void*)` with C linkage.
3. It must define and declare these three C++ functions:

    1. A serializer function

        ```c++
        nlohmann:json Serialize_vtkClassName(vtkObjectBase*, vtkSerializer*)
        ```
    2. A deserializer function

        ```c++
        void Deserialize_vtkClassName(const nlohmann::json&, vtkObjectBase*, vtkDeserializer*)
        ```
    3. A registrar function

        ```c++
        int RegisterHandlers_vtkClassNameSerDesHelper(void* ser, void* deser)
        ```
        that registers:
        - a serializer function with a serializer instance
        - a deserializer function with a deserializer instance
        - a constructor of the VTK class with a deserializer instance

## Properties

### Excluding properties

You can exclude certain properties of a class by simply annotating the relevant setter/getter functions
with `VTK_MARSHALEXCLUDE(reason)`, where reason is one of `VTK_MARSHAL_EXCLUDE_REASON_IS_INTERNAL` or
`VTK_MARSHAL_EXCLUDE_REASON_NOT_SUPPORTED`. This reason will be printed in the generated
C++ source code explaining why the property was not serialized.

## Custom get/set functions

Some properties may not be correctly recognized by the property parser because
they have different names for their get and set functions. You can override this
by annotating the get function with the `VTK_MARSHALGETTER(property)` macro. Doing
so will ensure that the function gets recognized as a getter for `property`.
`VTK_MARSHALSETTER(property)` serves a similar purpose.
