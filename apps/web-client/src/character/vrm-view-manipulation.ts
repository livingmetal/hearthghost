import { VRM_CAMERA_FRAMING } from "./vrm-framing.js";

export interface VrmViewState {
  readonly offsetX: number;
  readonly offsetY: number;
  readonly cameraZ: number;
}

interface PointerPosition {
  readonly x: number;
  readonly y: number;
}

interface PinchState {
  readonly distance: number;
  readonly cameraZ: number;
}

const MAX_HORIZONTAL_OFFSET = 0.58;
const MAX_VERTICAL_OFFSET = 0.42;
const MIN_CAMERA_Z = 2.10;
const MAX_CAMERA_Z = 3.40;
const DRAG_WORLD_SPAN = 0.92;
const WHEEL_ZOOM_PER_PIXEL = 0.0022;

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

function pointerDistance(pointers: ReadonlyMap<number, PointerPosition>): number | null {
  const [first, second] = Array.from(pointers.values());
  if (first === undefined || second === undefined) {
    return null;
  }
  return Math.hypot(second.x - first.x, second.y - first.y);
}

export class VrmViewManipulation {
  private readonly pointers = new Map<number, PointerPosition>();
  private pinch: PinchState | null = null;
  private offsetX = 0;
  private offsetY = 0;
  private cameraZ = VRM_CAMERA_FRAMING.cameraZ;

  snapshot(): VrmViewState {
    return {
      offsetX: this.offsetX,
      offsetY: this.offsetY,
      cameraZ: this.cameraZ,
    };
  }

  beginPointer(pointerId: number, x: number, y: number): void {
    this.pointers.set(pointerId, { x, y });
    if (this.pointers.size === 2) {
      const distance = pointerDistance(this.pointers);
      this.pinch = distance === null || distance <= 0
        ? null
        : { distance, cameraZ: this.cameraZ };
    }
  }

  movePointer(
    pointerId: number,
    x: number,
    y: number,
    viewportWidth: number,
    viewportHeight: number,
  ): VrmViewState {
    const previous = this.pointers.get(pointerId);
    if (previous === undefined || viewportWidth <= 0 || viewportHeight <= 0) {
      return this.snapshot();
    }
    this.pointers.set(pointerId, { x, y });

    if (this.pointers.size === 1) {
      this.offsetX = clamp(
        this.offsetX + ((x - previous.x) / viewportWidth) * DRAG_WORLD_SPAN,
        -MAX_HORIZONTAL_OFFSET,
        MAX_HORIZONTAL_OFFSET,
      );
      this.offsetY = clamp(
        this.offsetY - ((y - previous.y) / viewportHeight) * DRAG_WORLD_SPAN,
        -MAX_VERTICAL_OFFSET,
        MAX_VERTICAL_OFFSET,
      );
    } else if (this.pointers.size === 2 && this.pinch !== null) {
      const distance = pointerDistance(this.pointers);
      if (distance !== null && distance > 0) {
        this.cameraZ = clamp(
          this.pinch.cameraZ * (this.pinch.distance / distance),
          MIN_CAMERA_Z,
          MAX_CAMERA_Z,
        );
      }
    }
    return this.snapshot();
  }

  endPointer(pointerId: number): void {
    this.pointers.delete(pointerId);
    this.pinch = null;
  }

  zoomByWheel(deltaPixels: number): VrmViewState {
    this.cameraZ = clamp(
      this.cameraZ + deltaPixels * WHEEL_ZOOM_PER_PIXEL,
      MIN_CAMERA_Z,
      MAX_CAMERA_Z,
    );
    return this.snapshot();
  }

  nudge(horizontal: number, vertical: number, zoom: number): VrmViewState {
    this.offsetX = clamp(
      this.offsetX + horizontal,
      -MAX_HORIZONTAL_OFFSET,
      MAX_HORIZONTAL_OFFSET,
    );
    this.offsetY = clamp(
      this.offsetY + vertical,
      -MAX_VERTICAL_OFFSET,
      MAX_VERTICAL_OFFSET,
    );
    this.cameraZ = clamp(this.cameraZ + zoom, MIN_CAMERA_Z, MAX_CAMERA_Z);
    return this.snapshot();
  }

  reset(): VrmViewState {
    this.pointers.clear();
    this.pinch = null;
    this.offsetX = 0;
    this.offsetY = 0;
    this.cameraZ = VRM_CAMERA_FRAMING.cameraZ;
    return this.snapshot();
  }
}
