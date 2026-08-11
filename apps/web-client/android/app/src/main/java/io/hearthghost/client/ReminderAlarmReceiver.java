package io.hearthghost.client;

import android.Manifest;
import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;

/** Displays only a fixed redacted reminder notification. */
public final class ReminderAlarmReceiver extends BroadcastReceiver {
    private static final String CHANNEL_ID = "hearthghost-reminders";
    private static final String TITLE = "HearthGhost";
    private static final String BODY = "Reminder";

    @Override
    public void onReceive(Context context, Intent intent) {
        String reminderId = LocalReminderStore.reminderIdFromIntent(intent);
        if (reminderId == null || !notificationPermissionGranted(context)) {
            return;
        }
        NotificationManager manager =
            (NotificationManager) context.getSystemService(Context.NOTIFICATION_SERVICE);
        if (manager == null) {
            return;
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel channel = new NotificationChannel(
                CHANNEL_ID,
                "HearthGhost reminders",
                NotificationManager.IMPORTANCE_DEFAULT
            );
            channel.setDescription("Redacted local HearthGhost reminder notifications");
            manager.createNotificationChannel(channel);
        }
        Notification.Builder builder = Build.VERSION.SDK_INT >= Build.VERSION_CODES.O
            ? new Notification.Builder(context, CHANNEL_ID)
            : new Notification.Builder(context);
        Notification notification = builder
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .setContentTitle(TITLE)
            .setContentText(BODY)
            .setAutoCancel(true)
            .setCategory(Notification.CATEGORY_REMINDER)
            .build();
        manager.notify(reminderId, 1, notification);
    }

    static boolean notificationPermissionGranted(Context context) {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
            || context.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                == PackageManager.PERMISSION_GRANTED;
    }
}
