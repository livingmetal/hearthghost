package io.hearthghost.client;

import android.Manifest;
import android.os.Build;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;
import com.getcapacitor.PermissionState;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;
import com.getcapacitor.annotation.Permission;
import com.getcapacitor.annotation.PermissionCallback;

import org.json.JSONObject;

import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@CapacitorPlugin(
    name = "LocalReminder",
    permissions = {
        @Permission(
            alias = "notifications",
            strings = { Manifest.permission.POST_NOTIFICATIONS }
        )
    }
)
public final class LocalReminderPlugin extends Plugin {
    private static final long TOUCH_GATE_MILLIS = 2_000L;
    private LocalReminderStore store;

    @Override
    public void load() {
        store = new LocalReminderStore(getContext());
    }

    @PluginMethod
    public void status(PluginCall call) {
        call.resolve(statusOutput());
    }

    @PluginMethod
    public void requestNotificationPermission(PluginCall call) {
        if (!recentForegroundTouch()) {
            call.reject("notification_touch_gate_required");
            return;
        }
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) {
            call.resolve(statusOutput());
            return;
        }
        if (getPermissionState("notifications") == PermissionState.GRANTED) {
            call.resolve(statusOutput());
            return;
        }
        requestPermissionForAlias(
            "notifications",
            call,
            "notificationPermissionCallback"
        );
    }

    @PermissionCallback
    private void notificationPermissionCallback(PluginCall call) {
        if (getPermissionState("notifications") != PermissionState.GRANTED) {
            call.reject("notification_permission_denied");
            return;
        }
        call.resolve(statusOutput());
    }

    @PluginMethod
    public void reconcile(PluginCall call) {
        if (!notificationPermissionGranted()) {
            call.reject("notification_permission_required");
            return;
        }
        JSArray schedules = call.getArray("schedules");
        if (schedules == null || schedules.length() > LocalReminderStore.MAX_SCHEDULES) {
            call.reject("reminder_schedule_list_invalid");
            return;
        }
        try {
            Map<String, LocalReminderStore.Schedule> desired = parseSchedules(schedules);
            int count = store.reconcile(desired, System.currentTimeMillis());
            call.resolve(
                new JSObject()
                    .put("scheduledCount", count)
                    .put("mode", "inexact_allow_while_idle")
                    .put("contentMode", "redacted")
            );
        } catch (Exception error) {
            call.reject("local_reminder_reconcile_failed");
        }
    }

    private Map<String, LocalReminderStore.Schedule> parseSchedules(JSArray schedules)
        throws Exception {
        Map<String, LocalReminderStore.Schedule> result = new HashMap<>();
        Set<String> identities = new HashSet<>();
        for (int index = 0; index < schedules.length(); index++) {
            JSONObject schedule = schedules.getJSONObject(index);
            requireExactFields(schedule, "reminderId", "fireAt");
            String reminderId = schedule.getString("reminderId");
            if (!UUID.fromString(reminderId).toString().equals(reminderId)) {
                throw new IllegalArgumentException("reminder id invalid");
            }
            String fireAt = schedule.getString("fireAt");
            long fireAtMillis;
            try {
                fireAtMillis = OffsetDateTime.parse(fireAt).toInstant().toEpochMilli();
            } catch (DateTimeParseException error) {
                throw new IllegalArgumentException("fire_at invalid", error);
            }
            String identity = reminderId + "\n" + fireAtMillis;
            if (!identities.add(identity) || result.containsKey(reminderId)) {
                throw new IllegalArgumentException("duplicate reminder schedule");
            }
            result.put(
                reminderId,
                new LocalReminderStore.Schedule(reminderId, fireAtMillis)
            );
        }
        return result;
    }

    private void requireExactFields(JSONObject document, String... expected) {
        Set<String> actual = new HashSet<>();
        Iterator<String> keys = document.keys();
        while (keys.hasNext()) {
            actual.add(keys.next());
        }
        Set<String> required = new HashSet<>();
        java.util.Collections.addAll(required, expected);
        if (!actual.equals(required)) {
            throw new IllegalArgumentException("reminder schedule fields invalid");
        }
    }

    private boolean recentForegroundTouch() {
        if (!(getActivity() instanceof MainActivity)) {
            return false;
        }
        MainActivity activity = (MainActivity) getActivity();
        return activity.hasWindowFocus()
            && activity.hasRecentUserInteraction(TOUCH_GATE_MILLIS);
    }

    private boolean notificationPermissionGranted() {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU
            || getPermissionState("notifications") == PermissionState.GRANTED;
    }

    private JSObject statusOutput() {
        String permission = notificationPermissionGranted() ? "granted" : "prompt";
        return new JSObject()
            .put("permission", permission)
            .put("scheduledCount", store == null ? 0 : store.count())
            .put("mode", "inexact_allow_while_idle")
            .put("contentMode", "redacted")
            .put("exactAlarmPermissionRequired", false);
    }
}
