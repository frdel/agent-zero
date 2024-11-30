# Add getter and setter functions for the text on the buttons of vtkCameraOrientationRepresentation

You can now customize the text displayed on top of the buttons of a `vtkCameraOrientationRepresentation` using these functions

1. vtkCameraOrientationRepresentation::SetXPlusLabelText(const std::string& label)
2. vtkCameraOrientationRepresentation::SetXMinusLabelText(const std::string& label)
3. vtkCameraOrientationRepresentation::SetYPlusLabelText(const std::string& label)
4. vtkCameraOrientationRepresentation::SetYMinusLabelText(const std::string& label)
5. vtkCameraOrientationRepresentation::SetZPlusLabelText(const std::string& label)
6. vtkCameraOrientationRepresentation::SetZMinusLabelText(const std::string& label)

These methods follow similar naming convention to the existing getter methods for the `vtkTextProperty`
corresponding to the button labels.
