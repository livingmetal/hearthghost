package io.hearthghost.client;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

/** Stores only redacted schedule identity and reconciles inexact OS alarms. */
final class LocalReminderStore {
    static final int MAX_SCHEDULES = 100;
    private static final String PREFERENCES = "hearthghost.local.reminders.v1";
    private static final String URI_SCHEME = "hearthghost";
    private static final String URI_HOST = "reminder";

    static final class Schedule {
        final String reminderId;
        final long fireAtMillis;

        Schedule(String reminderId, long fireAtMillis) {
            requireCanonicalUuid(reminderId);
            if (fireAtMillis <= 0) {
                throw new IllegalArgumentException("fireAtMillis is invalid");
            }
            this.reminderId = reminderId;
            this.fireAtMillis = fireAtMillis;
        }
    }

    private final Context context;
    private final SharedPreferences preferences;
    private final AlarmManager alarms;

    LocalReminderStore(Context context) {
        this.context = context.getApplicationContext();
        this.preferences = this.context.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE);
        this.alarms = (AlarmManager) this.context.getSystemService(Context.ALARM_SERVICE);
        if (alarms == null) {
            throw new IllegalStateException("AlarmManager unavailable");
        }
    }

    synchronized int reconcile(Map<String, Schedule> desired, long nowMillis) {
        if (desired == null || desired.size() > MAX_SCHEDULES || nowMillis <= 0) {
            throw new IllegalArgumentException("local reminder reconcile input is invalid");
        }
        Map<String, Long> current = loadValid();
        Set<String> seen = new HashSet<>();
        for (Map.Entry<String, Schedule> entry : desired.entrySet()) {
            Schedule schedule = entry.getValue();
            if (
                schedule == null
                || !entry.getKey().equals(schedule.reminderId)
                || !seen.add(schedule.reminderId)
                || schedule.fireAtMillis <= nowMillis
            ) {
                throw new IllegalArgumentException("local reminder schedule is invalid");
            }
        }

        for (Map.Entry<String, Long> entry : current.entrySet()) {
            Schedule next = desired.get(entry.getKey());
            if (next == null || next.fireAtMillis != entry.getValue()) {
                cancel(entry.getKey(), entry.getValue());
            }
        }
        for (Schedule schedule : desired.values()) {
            Long previous = current.get(schedule.reminderId);
            if (previous == null || previous.longValue() != schedule.fireAtMillis) {
                schedule(schedule);
            }
        }

        SharedPreferences.Editor editor = preferences.edit().clear();
        for (Schedule schedule : desired.values()) {
            editor.putLong(schedule.reminderId, schedule.fireAtMillis);
        }
        if (!editor.commit()) {
            throw new IllegalStateException("local reminder metadata persistence failed");
        }
        return desired.size();
    }

    synchronized int restoreFuture(long nowMillis) {
        Map<String, Long> current = loadValid();
        Map<String, Schedule> future = new HashMap<>();
        for (Map.Entry<String, Long> entry : current.entrySet()) {
            if (entry.getValue() > nowMillis) {
                Schedule schedule = new Schedule(entry.getKey(), entry.getValue());
                schedule(schedule);
                future.put(entry.getKey(), schedule);
            } else {
                cancel(entry.getKey(), entry.getValue());
            }
        }
        SharedPreferences.Editor editor = preferences.edit().clear();
        for (Schedule schedule : future.values()) {
            editor.putLong(schedule.reminderId, schedule.fireAtMillis);
        }
        editor.commit();
        return future.size();
    }

    synchronized int count() {
        return loadValid().size();
    }

    private Map<String, Long> loadValid() {
        Map<String, Long> result = new HashMap<>();
        for (Map.Entry<String, ?> entry : preferences.getAll().entrySet()) {
            Object value = entry.getValue();
            if (!(value instanceof Long)) {
                continue;
            }
            try {
                requireCanonicalUuid(entry.getKey());
            } catch (IllegalArgumentException error) {
                continue;
            }
            long fireAt = (Long) value;
            if (fireAt > 0) {
                result.put(entry.getKey(), fireAt);
            }
        }
        return result;
    }

    private void schedule(Schedule schedule) {
        alarms.setAndAllowWhileIdle(
            AlarmManager.RTC_WAKEUP,
            schedule.fireAtMillis,
            pendingIntent(schedule.reminderId, schedule.fireAtMillis, PendingIntent.FLAG_UPDATE_CURRENT)
        );
    }

    private void cancel(String reminderId, long fireAtMillis) {
        PendingIntent pending = pendingIntent(
            reminderId,
            fireAtMillis,
            PendingIntent.FLAG_NO_CREATE
        );
        if (pending != null) {
            alarms.cancel(pending);
            pending.cancel();
        }
    }

    private PendingIntent pendingIntent(String reminderId, long fireAtMillis, int behaviorFlag) {
        Intent intent = new Intent(context, ReminderAlarmReceiver.class);
        intent.setData(
            new Uri.Builder()
                .scheme(URI_SCHEME)
                .authority(URI_HOST)
                .appendPath(reminderId)
                .appendQueryParameter("at", Long.toString(fireAtMillis))
                .build()
        );
        return PendingIntent.getBroadcast(
            context,
            0,
            intent,
            behaviorFlag | PendingIntent.FLAG_IMMUTABLE
        );
    }

    static String reminderIdFromIntent(Intent intent) {
        if (intent == null || intent.getData() == null) {
            return null;
        }
        Uri data = intent.getData();
        if (!URI_SCHEME.equals(data.getScheme()) || !URI_HOST.equals(data.getHost())) {
            return null;
        }
        java.util.List<String> segments = data.getPathSegments();
        if (segments.size() != 1) {
            return null;
        }
        String reminderId = segments.get(0);
        try {
            requireCanonicalUuid(reminderId);
        } catch (IllegalArgumentException error) {
            return null;
        }
        return reminderId;
    }

    private static void requireCanonicalUuid(String value) {
        if (value == null || !UUID.fromString(value).toString().equals(value)) {
            throw new IllegalArgumentException("reminderId is invalid");
        }
    }
}
