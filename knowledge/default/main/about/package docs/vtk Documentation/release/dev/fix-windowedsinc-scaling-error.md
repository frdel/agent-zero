## Fix scaling error in vtkWindowedSincPolyDataFilter

The filter used Hamming window function for low-pass filtering, which resulted in slight change (up to 1%)
in the overall size of the smoothed output (either larger or smaller)

Added the option to use Nuttall, Blackman, or Hanning window function that does not suffer from this error,
and changed the default to Nuttall, as it consistently performed better (accurate smoothing with less iterations) than all the others.

See more details in this discussion: https://discourse.vtk.org/t/slight-offset-in-vtkwindowedsincpolydatafilter-if-normalization-is-enabled/7676
