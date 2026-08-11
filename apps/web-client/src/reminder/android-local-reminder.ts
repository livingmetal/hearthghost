import { registerPlugin } from "@capacitor/core";

import type { RedactedReminderSchedule } from "../node/android-platform.js";

export interface LocalReminderStatus {
  readonly permission: "granted" | "prompt";
  readonly scheduledCount: number;
  readonly mode: "inexact_allow_while_idle";
  readonly contentMode: "redacted";
  readonly exactAlarmPermissionRequired: false;
}

interface LocalReminderNativePlugin {
  status(): Promise<LocalReminderStatus>;
  requestNotificationPermission(): Promise<LocalReminderStatus>;
  reconcile(options: {
    readonly schedules: readonly RedactedReminderSchedule[];
  }): Promise<{
    readonly scheduledCount: number;
    readonly mode: "inexact_allow_while_idle";
    readonly contentMode: "redacted";
  }>;
}

const NativeLocalReminder = registerPlugin<LocalReminderNativePlugin>(
  "LocalReminder",
);

export class AndroidLocalReminder {
  status(): Promise<LocalReminderStatus> {
    return NativeLocalReminder.status();
  }

  requestPermission(): Promise<LocalReminderStatus> {
    return NativeLocalReminder.requestNotificationPermission();
  }

  async reconcile(
    schedules: readonly RedactedReminderSchedule[],
  ): Promise<number> {
    if (!Array.isArray(schedules) || schedules.length > 100) {
      throw new Error("Reminder schedule list is invalid");
    }
    const result = await NativeLocalReminder.reconcile({ schedules });
    if (
      result.mode !== "inexact_allow_while_idle"
      || result.contentMode !== "redacted"
      || !Number.isInteger(result.scheduledCount)
      || result.scheduledCount < 0
      || result.scheduledCount > 100
    ) {
      throw new Error("Local reminder reconciliation result is invalid");
    }
    return result.scheduledCount;
  }
}
