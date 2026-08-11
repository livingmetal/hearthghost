package io.hearthghost.client;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Restores only future redacted local alarm metadata after device reboot. */
public final class ReminderBootReceiver extends BroadcastReceiver {
    @Override
    public void onReceive(Context context, Intent intent) {
        if (intent == null || !Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())) {
            return;
        }
        try {
            new LocalReminderStore(context).restoreFuture(System.currentTimeMillis());
        } catch (RuntimeException ignored) {
            // Fail closed: do not manufacture schedules when local state is invalid.
        }
    }
}
