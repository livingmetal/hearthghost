import {
  AnimationClip,
  AnimationMixer,
  LoopRepeat,
  VectorKeyframeTrack,
  type AnimationAction,
  type Object3D,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import type { VRM } from "@pixiv/three-vrm";
import {
  createVRMAnimationHumanoidTracks,
  VRMAnimationLoaderPlugin,
  type VRMAnimation,
} from "@pixiv/three-vrm-animation";

import type { CharacterState } from "./semantic.js";

export const BUNDLED_IDLE_VRMA_URL = "/animations/airi-idle-loop.vrma";

const MAX_HIPS_DELTA_X = 0.055;
const MAX_HIPS_DELTA_UP = 0.050;
const MAX_HIPS_DELTA_DOWN = 0.030;
const MAX_HIPS_DELTA_Z = 0.035;
const BLEND_RESPONSE = 3.4;

interface VrmAnimationGltfUserData {
  readonly vrmAnimations?: VRMAnimation[];
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.max(minimum, Math.min(maximum, value));
}

export function targetBaseAnimationWeight(state: CharacterState): number {
  switch (state) {
    case "sleeping":
      return 0.12;
    case "thinking":
      return 0.42;
    case "listening":
      return 0.72;
    case "engaged":
      return 0.78;
    case "noticing":
      return 0.86;
    case "speaking":
      return 0.68;
  }
}

/**
 * Anchor a VRMA hips translation to the current model and bound it to a small
 * idle envelope. This preserves authored weight transfer without allowing an
 * idle clip to walk the avatar across the stage.
 */
export function reanchorHipsPositionTrack(
  track: VectorKeyframeTrack,
  restPosition: readonly [number, number, number],
): VectorKeyframeTrack {
  const anchored = track.clone();
  if (anchored.values.length < 3) {
    return anchored;
  }
  const firstX = anchored.values[0] ?? 0;
  const firstY = anchored.values[1] ?? 0;
  const firstZ = anchored.values[2] ?? 0;
  for (let index = 0; index + 2 < anchored.values.length; index += 3) {
    const deltaX = (anchored.values[index] ?? firstX) - firstX;
    const deltaY = (anchored.values[index + 1] ?? firstY) - firstY;
    const deltaZ = (anchored.values[index + 2] ?? firstZ) - firstZ;
    anchored.values[index] = restPosition[0]
      + clamp(deltaX, -MAX_HIPS_DELTA_X, MAX_HIPS_DELTA_X);
    anchored.values[index + 1] = restPosition[1]
      + clamp(deltaY, -MAX_HIPS_DELTA_DOWN, MAX_HIPS_DELTA_UP);
    anchored.values[index + 2] = restPosition[2]
      + clamp(deltaZ, -MAX_HIPS_DELTA_Z, MAX_HIPS_DELTA_Z);
  }
  return anchored;
}

function baseOnlyClip(animation: VRMAnimation, vrm: VRM): AnimationClip {
  const humanoid = createVRMAnimationHumanoidTracks(
    animation,
    vrm.humanoid,
    vrm.meta.metaVersion,
  );
  const hips = vrm.humanoid.getNormalizedBoneNode("hips");
  const hipsRest: readonly [number, number, number] = hips === null
    ? [0, 0, 0]
    : [hips.position.x, hips.position.y, hips.position.z];
  const translation = humanoid.translation.get("hips");
  const tracks = [
    ...(translation === undefined
      ? []
      : [reanchorHipsPositionTrack(translation, hipsRest)]),
    ...Array.from(humanoid.rotation.values(), (track) => track.clone()),
  ];
  return new AnimationClip("hearthghost-idle-base", animation.duration, tracks);
}

export class VrmBaseAnimationLayer {
  private mixer: AnimationMixer | null = null;
  private action: AnimationAction | null = null;
  private clip: AnimationClip | null = null;
  private root: Object3D | null = null;
  private weight = 0;

  get isReady(): boolean {
    return this.mixer !== null && this.action !== null;
  }

  async load(vrm: VRM, url = BUNDLED_IDLE_VRMA_URL): Promise<void> {
    this.dispose();
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMAnimationLoaderPlugin(parser));
    const gltf = await loader.loadAsync(url);
    const animations = (gltf.userData as VrmAnimationGltfUserData).vrmAnimations;
    const animation = animations?.[0];
    if (animation === undefined) {
      throw new Error("VRMA asset does not contain a VRM animation");
    }

    const clip = baseOnlyClip(animation, vrm);
    if (clip.tracks.length === 0) {
      throw new Error("VRMA base animation has no usable humanoid tracks");
    }

    const mixer = new AnimationMixer(vrm.scene);
    const action = mixer.clipAction(clip);
    action.enabled = true;
    action.clampWhenFinished = false;
    action.setLoop(LoopRepeat, Infinity);
    action.setEffectiveWeight(0);
    action.play();

    this.mixer = mixer;
    this.action = action;
    this.clip = clip;
    this.root = vrm.scene;
    this.weight = 0;
  }

  update(delta: number, state: CharacterState): boolean {
    const mixer = this.mixer;
    const action = this.action;
    if (mixer === null || action === null) {
      return false;
    }
    const boundedDelta = Math.max(0, Math.min(delta, 0.1));
    const target = targetBaseAnimationWeight(state);
    const blend = 1 - Math.exp(-BLEND_RESPONSE * boundedDelta);
    this.weight += (target - this.weight) * blend;
    action.setEffectiveWeight(this.weight);
    mixer.update(boundedDelta);
    return true;
  }

  dispose(): void {
    if (this.mixer !== null) {
      this.mixer.stopAllAction();
      if (this.clip !== null) {
        this.mixer.uncacheClip(this.clip);
      }
      if (this.root !== null) {
        this.mixer.uncacheRoot(this.root);
      }
    }
    this.mixer = null;
    this.action = null;
    this.clip = null;
    this.root = null;
    this.weight = 0;
  }
}
