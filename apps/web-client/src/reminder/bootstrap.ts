import { Capacitor } from "@capacitor/core";

import { AndroidNodePlatform } from "../node/android-platform.js";
import { AndroidLocalReminder } from "./android-local-reminder.js";

const REMINDER_STATUS_ATTRIBUTE = "data-reminder-status";
const REMINDER_BUTTON_ATTRIBUTE = "data-reminder-enable";

if (Capacitor.getPlatform() === "android") {
  void mountWhenReady();
}

async function mountWhenReady(): Promise<void> {
  const root = await waitForElement("#app .top-actions");
  const statusBar = document.querySelector<HTMLElement>("#app .status-bar");
  if (root === null || statusBar === null) {
    return;
  }
  if (document.querySelector(`[${REMINDER_BUTTON_ATTRIBUTE}]`) !== null) {
    return;
  }

  const platform = new AndroidNodePlatform();
  const local = new AndroidLocalReminder();
  const button = document.createElement("button");
  button.type = "button";
  button.className = "quiet-button";
  button.setAttribute(REMINDER_BUTTON_ATTRIBUTE, "");
  button.textContent = "Enable reminders";
  root.prepend(button);

  const status = document.createElement("span");
  status.setAttribute(REMINDER_STATUS_ATTRIBUTE, "");
  status.textContent = "Notifications: checking";
  statusBar.append(status);

  const refresh = async (requestPermission: boolean): Promise<void> => {
    try {
      let localStatus = await local.status();
      if (requestPermission && localStatus.permission !== "granted") {
        localStatus = await local.requestPermission();
      }
      if (localStatus.permission !== "granted") {
        status.textContent = "Notifications: permission required";
        button.textContent = "Enable reminders";
        return;
      }
      const schedules = await platform.syncReminders();
      const count = await local.reconcile(schedules);
      status.textContent = `Notifications: ${count} local reminder${count === 1 ? "" : "s"}`;
      button.textContent = "Sync reminders";
    } catch {
      status.textContent = "Notifications: sync unavailable";
      button.textContent = "Sync reminders";
    }
  };

  button.addEventListener("click", () => {
    void refresh(true);
  });
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
      void refresh(false);
    }
  });
  await refresh(false);
}

async function waitForElement(selector: string): Promise<HTMLElement | null> {
  const existing = document.querySelector<HTMLElement>(selector);
  if (existing !== null) {
    return existing;
  }
  return new Promise((resolve) => {
    const observer = new MutationObserver(() => {
      const found = document.querySelector<HTMLElement>(selector);
      if (found !== null) {
        observer.disconnect();
        resolve(found);
      }
    });
    observer.observe(document.documentElement, { childList: true, subtree: true });
    window.setTimeout(() => {
      observer.disconnect();
      resolve(document.querySelector<HTMLElement>(selector));
    }, 5_000);
  });
}
