## CompositeDataset: Add Global Data

In ``dataset_adapter``, CompositeDataset can now access the Global Data, i.e. the FieldData of its root.

Example accessing the Global Data and the FieldData of a CompositeDataset:

```python
# Access the Global Data,  of the CompositeDataset
input.GlobalData["NSTEPS"].GetValue(0)
# Access the FieldData of the CompositeDataset
input.FieldData["AverageTemperature"].GetArrays()[0].GetValue(0)
```
