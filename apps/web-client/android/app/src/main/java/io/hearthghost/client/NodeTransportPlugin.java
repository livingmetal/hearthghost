package io.hearthghost.client;

import com.getcapacitor.JSObject;
import com.getcapacitor.Plugin;
import com.getcapacitor.PluginCall;
import com.getcapacitor.PluginMethod;
import com.getcapacitor.annotation.CapacitorPlugin;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.RejectedExecutionException;
import java.util.concurrent.atomic.AtomicBoolean;

@CapacitorPlugin(name = "NodeTransport")
public final class NodeTransportPlugin extends Plugin {
    private final ExecutorService operations = Executors.newSingleThreadExecutor();
    private final AtomicBoolean operationInFlight = new AtomicBoolean(false);
    private NodeIdentityStore identity;
    private NodeConnection connection;

    @Override
    public void load() {
        identity = new NodeIdentityStore(getContext());
        connection = new NodeConnection(identity);
    }

    @PluginMethod
    public void identityStatus(PluginCall call) {
        execute(call, () -> statusOutput(identity.status()));
    }

    @PluginMethod
    public void createEnrollmentRequest(PluginCall call) {
        execute(call, () -> {
            NodeIdentityStore.EnrollmentRequest request =
                identity.createEnrollmentRequest();
            return new JSObject()
                .put("nodeId", NodeIdentityStore.NODE_ID)
                .put(
                    "credentialReference",
                    NodeIdentityStore.CREDENTIAL_REFERENCE
                )
                .put("csrPem", request.pem)
                .put("csrSha256", request.sha256);
        });
    }

    @PluginMethod
    public void installCertificateChain(PluginCall call) {
        String nodeCertificate = call.getString("nodeCertificatePem");
        String authorityCertificate = call.getString("authorityCertificatePem");
        execute(
            call,
            () -> statusOutput(
                identity.installCertificateChain(
                    nodeCertificate,
                    authorityCertificate
                )
            )
        );
    }

    @PluginMethod
    public void connect(PluginCall call) {
        execute(call, connection::connect);
    }

    @PluginMethod
    public void disconnect(PluginCall call) {
        execute(call, () -> {
            connection.disconnect();
            return new JSObject();
        });
    }

    @PluginMethod
    public void openConversation(PluginCall call) {
        String nodeSessionId = call.getString("nodeSessionId");
        execute(call, () -> connection.openConversation(nodeSessionId));
    }

    @PluginMethod
    public void sendText(PluginCall call) {
        String conversationSessionId = call.getString("conversationSessionId");
        String text = call.getString("text");
        execute(
            call,
            () -> connection.sendText(conversationSessionId, text)
        );
    }

    @PluginMethod
    public void closeConversation(PluginCall call) {
        String conversationSessionId = call.getString("conversationSessionId");
        execute(
            call,
            () -> connection.closeConversation(conversationSessionId)
        );
    }

    @Override
    protected void handleOnDestroy() {
        if (connection != null) {
            connection.disconnect();
        }
        operations.shutdownNow();
        super.handleOnDestroy();
    }

    private JSObject statusOutput(NodeIdentityStore.IdentityStatus status) {
        return new JSObject()
            .put("keyPresent", status.keyPresent)
            .put("certificateInstalled", status.certificateInstalled)
            .put("nonExportable", status.nonExportable)
            .put(
                "credentialReference",
                NodeIdentityStore.CREDENTIAL_REFERENCE
            );
    }

    private void execute(PluginCall call, Operation operation) {
        if (!operationInFlight.compareAndSet(false, true)) {
            call.reject("native_node_operation_in_flight");
            return;
        }
        try {
            operations.execute(() -> {
                try {
                    call.resolve(operation.run());
                } catch (NodeTransportException error) {
                    call.reject(error.reasonCode());
                } catch (Exception error) {
                    call.reject("native_node_operation_failed");
                } finally {
                    operationInFlight.set(false);
                }
            });
        } catch (RejectedExecutionException error) {
            operationInFlight.set(false);
            call.reject("native_node_operation_unavailable");
        }
    }

    @FunctionalInterface
    private interface Operation {
        JSObject run() throws Exception;
    }
}
