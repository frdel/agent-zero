# Object manager

## Serialization
You can register objects with a `vtkObjectManager` instance and call
`UpdateStatesFromObjects`, `GetState(identifier)` to obtain a serialized state of
the registered objects and all their dependency objects that are
serializable.

## Deserialization
You can register a json state (stringified) with a `vtkObjectManager` instance
and call `UpdateObjectsFromStates`, `GetObjectAtId(identifier)` to deserialize and
retrieve the objects.

## Blobs
All `vtkDataArray` are hashed and stored as unique blobs to prevent
multiple copies of the same data within the state. The contents of a data array
within a state are represented with a hash string. You can fetch and register
blobs using `GetBlob` and `RegisterBlob`.

## Dependencies
You can retrieve all dependent object identifiers using
`vtkObjectManager::GetAllDependencies(identifier)`
