# Auto serialization
Modules which have `INCLUDE_MARSHAL` in their `vtk.module` will opt their headers into the automated code generation of (de)serializers. Only classes which are annotated by the `VTK_MARSHALAUTO` wrapping hint will have generated serialization code.

## Automated code generation
The `vtkWrapSerDes` executable makes use of the `WrappingTools` package to automatically generate
1. A serializer function with signature
  `nlohmann:json Serialize_vtkClassName(vtkObjectBase*, vtkSerializer*)`
2. A deserializer function with signature
  `void(const nlohmann::json&, vtkObjectBase*, vtkDeserializer*)`
3. A registrar function that registers
    - the serializer function with a serializer instance
    - the deserializer function with a deserializer instance
    - the constructor of the VTK class with a deserializer instance
    - It's signature is
      `int RegisterHandlers_vtkClassNameSerDes(void* ser, void* deser)`
    - It more or less looks like:
      ```c++
      int RegisterHandlers_vtkObjectSerDes(void* ser, void* deser)
      {
        int success = 0;
        if (auto* asObjectBase = static_cast<vtkObjectBase*>(ser))
        {
          if (auto* serializer = vtkSerializer::SafeDownCast(asObjectBase))
          {
            serializer->RegisterHandler(typeid(vtkObject), Serialize_vtkObject);
            success = 1;
          }
        }
        if (auto* asObjectBase = static_cast<vtkObjectBase*>(deser))
        {
          if (auto* deserializer = vtkDeserializer::SafeDownCast(asObjectBase))
          {
            deserializer->RegisterHandler(typeid(vtkObject), Deserialize_vtkObject);
            deserializer->RegisterConstructor("vtkObject", []() { return vtkObject::New(); });
            success = 1;
          }
        }
        return success;
      }
      ```

## Marshal hint macro
  1. Classes which are annotated with `VTK_MARSHALAUTO` are considered by the `vtkWrapSerDes` executable.
  2. Classes annotated with `VTK_MARSHALMANUAL` are hand coded in the same module. Here are some examples:
     - `Common/Core/vtkCollectionSerDesHelper.cxx` for `Common/Core/vtkCollection.h`
     - `Common/DataModel/vtkCellArraySerDesHelper.cxx` for `Common/DataModel/vtkCellArray.h`

## Convenient script to annotate headers and module
- The [Utilities/Marshalling/marshal_macro_annotate_headers.py](../../../Utilities/Marshalling/marshal_macro_annotate_headers.py) script annotates headers for automatic or manual serialization. It is fed and driven by the accompanying [Utilities/Marshalling/VTK_MARSHALAUTO.txt](../../../Utilities/Marshalling/VTK_MARSHALAUTO.txt), [Utilities/Marshalling/VTK_MARSHALMANUAL.txt](../../../Utilities/Marshalling/VTK_MARSHALMANUAL.txt) and [Utilities/Marshalling/ignore.txt](../../../Utilities/Marshalling/ignore.txt).

- When the `-u, --update` argument is used, headers are in-place edited to use the `VTK_MARSHAL(AUTO|MANUAL)` wrapping hint. Files that already have this hint are untouched.

- When the `-t, --test` argument is used, the source tree is checked for inconsistent use of marshal macros.
