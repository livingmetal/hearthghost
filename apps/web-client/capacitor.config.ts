import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "io.hearthghost.client",
  appName: "HearthGhost",
  webDir: "dist",
  android: {
    allowMixedContent: false,
  },
};

export default config;
