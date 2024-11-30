### WebGPU Compute API - Hierarchical two-pass occlusion culling

Implementation of a hierarchical z-buffer occlusion culling algorithm using the WebGPU Compute API.
For very simple scenes with large numbers of cells (hundreds of millions), the WebGPU Occlusion culler
can outperform OpenGL + CPU Coverage Culling by an order of magnitude of 2x. These results were obtained
on a scene with very simple flat shading and further increases in performance could be observed with
more complex shading.
