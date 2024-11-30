# Golden Ball Source

A `vtkGoldenBallSource` algorithm has been added to provide
a method to construct a solid, tetrahedralized ball. It uses
a Fibonacci spiral (generated using the "Golden Angle" of
π(sqrt(5) - 1)) which is then projected out of the plane onto
a sphere and Delaunay-tetrahedralized into a ball. It
includes a "normal" vector field by default which is zero-length
at the center of the ball.

Besides the spiral construction this algorithm is also distinct
from the existing sphere source because it produces a solid
rather than a bounding surface.
