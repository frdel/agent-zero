## Change quadratic Wedge face normal orientation

vtkCell::GetFace should for 3d cells return faces with normals pointing outward.
This was not the case of vtkQuadraticWedge, vtkBiQuadraticQuadraticWedge and vtkQuadraticLinearWedge that is now fixed.
This fix a bug where the face between two elements of different types ( one quadratic wedge and the second one a quadratic hex for instance ) was rendered, whereas it was not supposed.
