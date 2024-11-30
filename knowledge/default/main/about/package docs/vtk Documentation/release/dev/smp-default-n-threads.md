## New `vtkSMPTools::GetEstimatedDefaultNumberOfThreads()` API

One can now know the default number of estimated threads available in a machine regardless
of the number of effective threads that VTK will run when running SMP tasks. By calling
`vtkSMPTools::Initialize(int nthreads)`, one can reduce the number of threads used by SMP.
This will change the return value of `vtkSMPTools::GetEstimatedNumberOfThreads()`, but
won't change the return value of `vtkSMPTools::GetEstimatedDefaultNumberOfThreads()`.
