package io.hearthghost.client;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(NodeTransportPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
