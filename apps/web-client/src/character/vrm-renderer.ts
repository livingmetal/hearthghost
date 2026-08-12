import {
  AmbientLight,
  Clock,
  DirectionalLight,
  Object3D,
  PerspectiveCamera,
  Scene,
  WebGLRenderer,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, VRMUtils, type VRM } from "@pixiv/three-vrm";

import type { CharacterRenderer } from "./renderer.js";
import type { CharacterEmotion, CharacterPresentation, CharacterState } from "./semantic.js";

interface BoneRestPose {
  readonly node: Object3D;
  readonly x: number;
  readonly y: number;
  readonly z: number;
}

type DrivenBoneName = "hips" | "spine" | "chest" | "neck" | "head";

const EMOTION_EXPRESSION_TARGETS: Readonly<Record<CharacterEmotion, Readonly<Record<string, number>>>> = Object.freeze({
  neutral: Object.freeze({}),
  happy: Object.freeze({ happy: 0.42 }),
  amused: Object.freeze({ happy: 0.34, relaxed: 0.12 }),
  curious: Object.freeze({ surprised: 0.12, happy: 0.05 }),
  concerned: Object.freeze({ sad: 0.26 }),
  surprised: Object.freeze({ surprised: 0.48 }),
});

export class VrmCharacterRenderer implements CharacterRenderer {
  private readonly scene = new Scene();
  private readonly camera = new PerspectiveCamera(30, 1, 0.1, 20);
  private readonly clock = new Clock();
  private readonly lookAtTarget = new Object3D();
  private readonly expressionValues = new Map<string, number>();
  private readonly expressionNames = new Map<string, string>();
  private readonly drivenBones = new Map<DrivenBoneName, BoneRestPose>();
  private renderer: WebGLRenderer | null = null;
  private vrm: VRM | null = null;
  private frame: number | null = null;
  private elapsed = 0;
  private nextBlinkAt = 2 + Math.random() * 2.5;
  private blinkElapsed = 0;
  private nextSaccadeAt = 1.2 + Math.random() * 2.2;
  private saccadeX = 0;
  private saccadeY = 0;
  private presentation: CharacterPresentation = {
    state: "sleeping",
    emotion: "neutral",
  };

  constructor(private readonly assetUrl: string | null = null) {
    this.camera.position.set(0, 1.42, 3);
    this.camera.lookAt(0, 1.35, 0);
    this.scene.add(new AmbientLight(0xffffff, 1.8));
    const keyLight = new DirectionalLight(0xffffff, 2.1);
    keyLight.position.set(1.2, 2.4, 2.6);
    this.scene.add(keyLight);
    this.lookAtTarget.position.set(0, 1.48, 3);
    this.scene.add(this.lookAtTarget);
  }

  async mount(viewport: HTMLElement): Promise<void> {
    this.renderer = new WebGLRenderer({ alpha: true, antialias: true });
    this.renderer.outputColorSpace = "srgb";
    if (this.assetUrl !== null) {
      await this.loadVrm(this.assetUrl);
    }
    viewport.replaceChildren(this.renderer.domElement);
    this.resume();
  }

  resize(width: number, height: number, pixelRatio: number): void {
    if (this.renderer === null || width <= 0 || height <= 0) {
      return;
    }
    this.renderer.setPixelRatio(Math.min(pixelRatio, 2));
    this.renderer.setSize(width, height, false);
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  present(presentation: CharacterPresentation): void {
    this.presentation = presentation;
  }

  suspend(): void {
    if (this.frame !== null) {
      cancelAnimationFrame(this.frame);
      this.frame = null;
    }
    this.clock.stop();
  }

  resume(): void {
    if (this.renderer === null || this.frame !== null) {
      return;
    }
    this.clock.start();
    this.frame = requestAnimationFrame(() => this.renderFrame());
  }

  dispose(): void {
    this.suspend();
    if (this.vrm !== null) {
      this.vrm.scene.removeFromParent();
      VRMUtils.deepDispose(this.vrm.scene);
    }
    this.vrm = null;
    this.drivenBones.clear();
    this.expressionNames.clear();
    this.expressionValues.clear();
    this.renderer?.dispose();
    this.renderer?.domElement.remove();
    this.renderer = null;
  }

  private async loadVrm(assetUrl: string): Promise<void> {
    const loader = new GLTFLoader();
    loader.register((parser) => new VRMLoaderPlugin(parser));
    const gltf = await loader.loadAsync(assetUrl);
    const vrm = gltf.userData.vrm as VRM | undefined;
    if (vrm === undefined) {
      throw new Error("The selected asset does not contain a VRM model");
    }

    VRMUtils.removeUnnecessaryVertices(gltf.scene);
    VRMUtils.combineSkeletons(gltf.scene);
    VRMUtils.combineMorphs(vrm);
    VRMUtils.rotateVRM0(vrm);

    if (this.vrm !== null) {
      this.vrm.scene.removeFromParent();
      VRMUtils.deepDispose(this.vrm.scene);
    }
    this.vrm = vrm;
    this.scene.add(vrm.scene);
    this.applyConversationPose(vrm);
    this.captureDrivenBones(vrm);
    this.indexExpressions(vrm);
    if (vrm.lookAt !== null) {
      vrm.lookAt.target = this.lookAtTarget;
    }
  }

  private applyConversationPose(vrm: VRM): void {
    const leftUpperArm = vrm.humanoid.getNormalizedBoneNode("leftUpperArm");
    const rightUpperArm = vrm.humanoid.getNormalizedBoneNode("rightUpperArm");
    if (leftUpperArm !== null) {
      leftUpperArm.rotation.z += 1.10;
      leftUpperArm.rotation.y -= 0.08;
    }
    if (rightUpperArm !== null) {
      rightUpperArm.rotation.z -= 1.10;
      rightUpperArm.rotation.y += 0.08;
    }

    const leftLowerArm = vrm.humanoid.getNormalizedBoneNode("leftLowerArm");
    const rightLowerArm = vrm.humanoid.getNormalizedBoneNode("rightLowerArm");
    if (leftLowerArm !== null) {
      leftLowerArm.rotation.y -= 0.12;
    }
    if (rightLowerArm !== null) {
      rightLowerArm.rotation.y += 0.12;
    }
  }

  private captureDrivenBones(vrm: VRM): void {
    this.drivenBones.clear();
    for (const name of ["hips", "spine", "chest", "neck", "head"] as const) {
      const node = vrm.humanoid.getNormalizedBoneNode(name);
      if (node === null) {
        continue;
      }
      this.drivenBones.set(name, {
        node,
        x: node.rotation.x,
        y: node.rotation.y,
        z: node.rotation.z,
      });
    }
  }

  private indexExpressions(vrm: VRM): void {
    this.expressionNames.clear();
    const manager = vrm.expressionManager;
    if (manager === null) {
      return;
    }
    for (const name of Object.keys(manager.expressionMap)) {
      this.expressionNames.set(name.toLowerCase(), name);
    }
  }

  private renderFrame(): void {
    this.frame = null;
    if (this.renderer === null) {
      return;
    }
    const delta = Math.min(this.clock.getDelta(), 0.1);
    this.elapsed += delta;
    if (this.vrm !== null) {
      this.updateBodyMotion(this.presentation.state, delta);
      this.updateLookAt(this.presentation.state, delta);
      this.updateExpressions(delta);
      this.updateBlink(delta);
      this.updateMouth(this.presentation.state, delta);
      this.vrm.update(delta);
    }
    this.renderer.render(this.scene, this.camera);
    this.frame = requestAnimationFrame(() => this.renderFrame());
  }

  private updateBodyMotion(state: CharacterState, _delta: number): void {
    const activity = state === "speaking"
      ? 1.35
      : state === "noticing"
        ? 1.15
        : state === "sleeping"
          ? 0.28
          : 0.8;
    const breath = Math.sin(this.elapsed * 1.8) * 0.012 * activity;
    const sway = Math.sin(this.elapsed * 0.72) * 0.012 * activity;
    const speakingNod = state === "speaking" ? Math.sin(this.elapsed * 3.4) * 0.014 : 0;
    const thinkingTilt = state === "thinking" ? 0.055 : 0;
    const sleepingDrop = state === "sleeping" ? 0.07 : 0;

    this.setBoneRotation("hips", 0, sway * 0.45, sway * 0.4);
    this.setBoneRotation("spine", breath * 0.55, sway * 0.38, -sway * 0.25);
    this.setBoneRotation("chest", breath, sway * 0.5, sway * 0.42);
    this.setBoneRotation("neck", sleepingDrop * 0.35, -sway * 0.35, thinkingTilt * 0.35);
    this.setBoneRotation("head", sleepingDrop + speakingNod, -sway * 0.6, thinkingTilt);
  }

  private setBoneRotation(name: DrivenBoneName, x: number, y: number, z: number): void {
    const rest = this.drivenBones.get(name);
    if (rest === undefined) {
      return;
    }
    rest.node.rotation.set(rest.x + x, rest.y + y, rest.z + z);
  }

  private updateLookAt(state: CharacterState, delta: number): void {
    if (
      state !== "sleeping"
      && state !== "thinking"
      && this.elapsed >= this.nextSaccadeAt
    ) {
      this.saccadeX = (Math.random() - 0.5) * 0.16;
      this.saccadeY = (Math.random() - 0.5) * 0.10;
      this.nextSaccadeAt = this.elapsed + 1.0 + Math.random() * 2.8;
    }
    const targetX = state === "thinking" ? 0.34 : state === "sleeping" ? 0 : this.saccadeX;
    const targetY = state === "sleeping"
      ? 1.28
      : state === "thinking"
        ? 1.62
        : 1.48 + this.saccadeY;
    const targetZ = 3;
    const blend = 1 - Math.exp(-4.5 * delta);
    this.lookAtTarget.position.x += (targetX - this.lookAtTarget.position.x) * blend;
    this.lookAtTarget.position.y += (targetY - this.lookAtTarget.position.y) * blend;
    this.lookAtTarget.position.z += (targetZ - this.lookAtTarget.position.z) * blend;
  }

  private updateExpressions(delta: number): void {
    const target = EMOTION_EXPRESSION_TARGETS[this.presentation.emotion] ?? EMOTION_EXPRESSION_TARGETS.neutral;
    for (const name of ["happy", "relaxed", "surprised", "sad"] as const) {
      const from = this.expressionValues.get(name) ?? 0;
      const to = target[name] ?? 0;
      const blend = 1 - Math.exp(-7 * delta);
      const value = from + (to - from) * blend;
      this.expressionValues.set(name, value);
      this.setExpression(name, value);
    }
  }

  private updateBlink(delta: number): void {
    this.blinkElapsed += delta;
    let blink = 0;
    if (this.presentation.state === "sleeping") {
      blink = 0.82;
    } else if (this.blinkElapsed >= this.nextBlinkAt) {
      const blinkProgress = (this.blinkElapsed - this.nextBlinkAt) / 0.18;
      if (blinkProgress >= 1) {
        this.blinkElapsed = 0;
        this.nextBlinkAt = 1.8 + Math.random() * 3.4;
      } else {
        blink = Math.sin(Math.PI * blinkProgress);
      }
    }
    this.setExpression("blink", blink);
  }

  private updateMouth(state: CharacterState, _delta: number): void {
    if (state !== "speaking") {
      this.setExpression("aa", 0);
      this.setExpression("ee", 0);
      this.setExpression("ih", 0);
      this.setExpression("oh", 0);
      this.setExpression("ou", 0);
      return;
    }
    const primary = (Math.sin(this.elapsed * 22) + 1) * 0.5;
    const secondary = (Math.sin(this.elapsed * 13.5 + 1.2) + 1) * 0.5;
    this.setExpression("aa", 0.08 + primary * 0.24);
    this.setExpression("ee", secondary * 0.06);
    this.setExpression("ih", (1 - secondary) * 0.04);
    this.setExpression("oh", (1 - primary) * 0.10);
    this.setExpression("ou", secondary * 0.035);
  }

  private setExpression(name: string, value: number): void {
    const manager = this.vrm?.expressionManager;
    if (manager === null || manager === undefined) {
      return;
    }
    const actualName = this.expressionNames.get(name.toLowerCase());
    if (actualName === undefined) {
      return;
    }
    manager.setValue(actualName, Math.max(0, Math.min(1, value)));
  }
}

export async function createVrmCharacterRenderer(
  assetUrl: string | null = null,
): Promise<CharacterRenderer> {
  return new VrmCharacterRenderer(assetUrl);
}
