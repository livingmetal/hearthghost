package io.hearthghost.client;

import android.os.Bundle;
import android.os.SystemClock;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    private volatile long lastUserInteractionElapsedRealtime = Long.MIN_VALUE;

    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(NodeTransportPlugin.class);
        registerPlugin(VoiceInputPlugin.class);
        registerPlugin(VoiceOutputPlugin.class);
        registerPlugin(LocalReminderPlugin.class);
        super.onCreate(savedInstanceState);
    }

    @Override
    public void onUserInteraction() {
        lastUserInteractionElapsedRealtime = SystemClock.elapsedRealtime();
        super.onUserInteraction();
    }

    boolean hasRecentUserInteraction(long maximumAgeMillis) {
        if (maximumAgeMillis <= 0) {
            return false;
        }
        long last = lastUserInteractionElapsedRealtime;
        if (last == Long.MIN_VALUE) {
            return false;
        }
        long age = SystemClock.elapsedRealtime() - last;
        return age >= 0 && age <= maximumAgeMillis;
    }
}
