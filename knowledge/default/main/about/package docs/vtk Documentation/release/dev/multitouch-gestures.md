## Multi-touch gestures in VTK

Multiple improvements have been introduced to the multi-touch event based gesture handling.

- Panning was compounding the translation causing a pan that would scale exponentially as it
  progresses.
- Pinch gesture was being handled by printing an error message.
- There was no "end" to the multi-touch events.
- The [Set/Get]CurrentGesture methods are moved to the vtkRenderWindowInteractor from its derived
  class vtkVRRenderWindowInteractor. This would allow client applications with custom interaction
  styles to redefine these APIs.
- [BREAKING CHANGE] Dynamic gesture detection
    Originally, once a gesture was detected, VTK would continue processing it for all future mouse
    move (touch move) events until the finger was lifted or mouse was released. This is fine for
    single touch gestures but for multitouch gestures, it is typically required to switch to
    different gestures with different motions. For example, the user could touch the screen, start
    pinching and without lifting the finger, start panning. Another common interaction is when the
    user starts panning but the pointer math initially guesses the gesture to be a pinch gesture.
    Originally execution would be stuck processing pinch even if the user's fingers are performing a
    pan. This change would ensure that gesture recognition eventually matches up with the user's
    intention.
