export interface VrmCameraFraming {
  readonly verticalFieldOfViewDegrees: number;
  readonly cameraX: number;
  readonly cameraY: number;
  readonly cameraZ: number;
  readonly targetY: number;
  readonly lookAtTargetY: number;
  readonly lookAtTargetZ: number;
  readonly forwardGestureOffset: number;
  readonly backwardGestureOffset: number;
}

// Conversation framing deliberately favors a waist-up character over the
// distant full-body composition used by the first renderer prototype. Keeping
// the values together also makes the closest supported gesture auditable.
export const VRM_CAMERA_FRAMING: Readonly<VrmCameraFraming> = Object.freeze({
  verticalFieldOfViewDegrees: 30,
  cameraX: 0,
  cameraY: 1.42,
  cameraZ: 2.58,
  targetY: 1.35,
  lookAtTargetY: 1.48,
  lookAtTargetZ: 2.58,
  forwardGestureOffset: 0.32,
  backwardGestureOffset: -0.24,
});

export function cameraClearanceAtForwardExtent(
  framing: VrmCameraFraming = VRM_CAMERA_FRAMING,
): number {
  return framing.cameraZ - framing.forwardGestureOffset;
}
