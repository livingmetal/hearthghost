import {
  AmbientLight,
  Clock,
  PerspectiveCamera,
  Scene,
  WebGLRenderer,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { VRMLoaderPlugin, type VRM } from "@pixiv/three-vrm";

import type { CharacterRenderer } from "./renderer.js";
import type { CharacterPresentation } from "./semantic.js";

export class VrmCharacterRenderer implements CharacterRenderer {
  private readonly scene = new Scene();
  private readonly camera = new PerspectiveCamera(30, 1, 0.1, 20);
  private readonly clock = new Clock();
  private renderer: WebGLRenderer | null = null;
  private vrm: VRM | null = null;
  private frame: number | null = null;
  private presentation: CharacterPresentation = {
    state: "sleeping",
    emotion: "neutral",
  };

  constructor(private readonly assetUrl: string | null = null) {
    this.camera.position.set(0, 1.4, 3);
    this.scene.add(new AmbientLight(0xffffff, 2.5));
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
    this.renderer.setPixelRatio(pixelRatio);
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
    this.vrm?.scene.removeFromParent();
    this.vrm = null;
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
    this.vrm?.scene.removeFromParent();
    this.vrm = vrm;
    this.scene.add(vrm.scene);
  }

  private renderFrame(): void {
    this.frame = null;
    if (this.renderer === null) {
      return;
    }
    const delta = Math.min(this.clock.getDelta(), 0.1);
    const activity = this.presentation.state === "speaking" ? 1 : 0;
    this.vrm?.expressionManager?.setValue("aa", activity * 0.18);
    this.vrm?.update(delta);
    this.renderer.render(this.scene, this.camera);
    this.frame = requestAnimationFrame(() => this.renderFrame());
  }
}

export async function createVrmCharacterRenderer(
  assetUrl: string | null = null,
): Promise<CharacterRenderer> {
  return new VrmCharacterRenderer(assetUrl);
}
