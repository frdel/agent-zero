## Simplify the customization for Kokkos backend

When using Kokkos, some Kokkos devices/backends require enabling a
language (such as CUDA or HIP). Previously, this required users to set a
variable named `VTK_KOKKOS_BACKEND` to an appropriate value. This is
simplified by getting the Kokkos backends directly from the Kokkos
configuration so that the compilers are set up automatically.
