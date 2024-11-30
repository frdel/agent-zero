# Adding support for specification of backend when using VTK-m w/ Kokkos

This change affects how `VTK` Accelerated Filters are build as they use `VTK-m`
It does away with the requirement of using flags like `VTK_USE_HIP` -- when actually `VTK-m`
is built with the necessary Kokkos backend. This also future-proofs the specification for backends.
Two new flags are introduced `VTK_USE_KOKKOS` and `VTK_KOKKOS_BACKEND` -- the first flag is considered
`ON` automatically if the backend flag is provided.

Here's how users can build with different backends

- `VTK_USE_CUDA` -- use the native CUDA support from VTK-m
- `VTK_USE_KOKKOS + VTK_KOKKOS_BACKEND=CUDA` or `VTK_KOKKOS_BACKEND=CUDA` will use Kokkos with CUDA backend
- `VTK_USE_KOKKOS + VTK_KOKKOS_BACKEND=SYCL` or `VTK_KOKKOS_BACKEND=SYCL` will use Kokkos with SYCL backend
- `VTK_USE_KOKKOS + VTK_KOKKOS_BACKEND=HIP` or `VTK_KOKKOS_BACKEND=HIP` will use Kokkos with HIP backend
- `VTK_USE_KOKKOS` will use Kokkos with Serial backend
