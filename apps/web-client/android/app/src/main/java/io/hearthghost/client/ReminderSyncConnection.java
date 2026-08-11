package io.hearthghost.client;

import com.getcapacitor.JSArray;
import com.getcapacitor.JSObject;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import java.security.Principal;
import java.security.PrivateKey;
import java.security.cert.X509Certificate;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.Arrays;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Set;
import java.util.UUID;

import javax.net.ssl.KeyManager;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLParameters;
import javax.net.ssl.SSLSocket;
import javax.net.ssl.TrustManagerFactory;
import javax.net.ssl.X509ExtendedKeyManager;

/** One-shot outbound mTLS sync for redacted local reminder schedules. */
final class ReminderSyncConnection {
    private static final String HOST = "192.168.55.100";
    private static final int PORT = 38443;
    private static final String CONTRACT_VERSION = "1.0";
    private static final String ALPN = "hearthghost-node/1";
    private static final String CAPABILITY = "notification.local";
    private static final int CONNECT_TIMEOUT_MILLIS = 5_000;
    private static final int SOCKET_TIMEOUT_MILLIS = 20_000;
    private static final int MAX_FRAME_BYTES = 16 * 1024;
    private static final int MAX_SCHEDULES = 100;

    private final NodeIdentityStore identity;

    ReminderSyncConnection(NodeIdentityStore identity) {
        this.identity = identity;
    }

    JSObject sync() throws Exception {
        NodeIdentityStore.IdentityStatus status = identity.status();
        if (!status.keyPresent || !status.certificateInstalled || !status.nonExportable) {
            throw new NodeTransportException("node_identity_not_provisioned");
        }
        try (SSLSocket socket = openSocket()) {
            DataInputStream input = new DataInputStream(socket.getInputStream());
            DataOutputStream output = new DataOutputStream(socket.getOutputStream());
            JSONObject opened = exchange(
                input,
                output,
                new JSONObject()
                    .put("contract_version", CONTRACT_VERSION)
                    .put("message_type", "session.open")
                    .put("request_id", UUID.randomUUID().toString())
                    .put("node_id", NodeIdentityStore.NODE_ID)
            );
            String nodeSessionId = requireAcceptedNodeResult(opened, "session.open");
            try {
                JSONObject capability = exchange(
                    input,
                    output,
                    new JSONObject()
                        .put("contract_version", CONTRACT_VERSION)
                        .put("message_type", "capability.request")
                        .put("request_id", UUID.randomUUID().toString())
                        .put("session_id", nodeSessionId)
                        .put("sequence", 1)
                        .put("capability", CAPABILITY)
                );
                requireAcceptedNodeResult(capability, "capability.request");

                String syncRequestId = UUID.randomUUID().toString();
                JSONObject result = exchange(
                    input,
                    output,
                    new JSONObject()
                        .put("contract_version", CONTRACT_VERSION)
                        .put("message_type", "reminder.sync")
                        .put("request_id", syncRequestId)
                        .put("node_session_id", nodeSessionId)
                        .put("sequence", 2)
                );
                return parseSyncResult(result, syncRequestId, nodeSessionId);
            } finally {
                try {
                    exchange(
                        input,
                        output,
                        new JSONObject()
                            .put("contract_version", CONTRACT_VERSION)
                            .put("message_type", "session.close")
                            .put("request_id", UUID.randomUUID().toString())
                            .put("session_id", nodeSessionId)
                    );
                } catch (Exception ignored) {
                    // The one-shot socket close is terminal even if explicit close fails.
                }
            }
        }
    }

    private SSLSocket openSocket() throws Exception {
        X509Certificate authority = identity.authorityCertificate();
        KeyStore trustStore = KeyStore.getInstance(KeyStore.getDefaultType());
        trustStore.load(null);
        trustStore.setCertificateEntry("hearthghost-development-ca", authority);
        TrustManagerFactory trustManagers = TrustManagerFactory.getInstance(
            TrustManagerFactory.getDefaultAlgorithm()
        );
        trustManagers.init(trustStore);
        KeyManager[] keyManagers = {
            new FixedAliasKeyManager(
                NodeIdentityStore.KEY_ALIAS,
                identity.privateKey(),
                identity.certificateChain()
            )
        };
        SSLContext context = SSLContext.getInstance("TLSv1.3");
        context.init(keyManagers, trustManagers.getTrustManagers(), null);
        SSLSocket socket = (SSLSocket) context.getSocketFactory().createSocket();
        try {
            socket.setUseClientMode(true);
            socket.setEnabledProtocols(new String[] { "TLSv1.3" });
            SSLParameters parameters = socket.getSSLParameters();
            parameters.setEndpointIdentificationAlgorithm("HTTPS");
            parameters.setApplicationProtocols(new String[] { ALPN });
            socket.setSSLParameters(parameters);
            socket.connect(new InetSocketAddress(HOST, PORT), CONNECT_TIMEOUT_MILLIS);
            socket.setSoTimeout(SOCKET_TIMEOUT_MILLIS);
            socket.startHandshake();
            if (
                !"TLSv1.3".equals(socket.getSession().getProtocol())
                || !ALPN.equals(socket.getApplicationProtocol())
                || socket.getSession().getPeerCertificates().length == 0
            ) {
                throw new NodeTransportException("tls_profile_not_negotiated");
            }
            return socket;
        } catch (Exception error) {
            try {
                socket.close();
            } catch (Exception ignored) {
                // Preserve the original connection error.
            }
            throw error;
        }
    }

    private JSONObject exchange(
        DataInputStream input,
        DataOutputStream output,
        JSONObject request
    ) throws Exception {
        byte[] payload = request.toString().getBytes(StandardCharsets.UTF_8);
        if (payload.length < 1 || payload.length > MAX_FRAME_BYTES) {
            throw new NodeTransportException("outbound_frame_invalid");
        }
        output.writeInt(payload.length);
        output.write(payload);
        output.flush();
        int length = input.readInt();
        if (length < 1 || length > MAX_FRAME_BYTES) {
            throw new NodeTransportException("inbound_frame_invalid");
        }
        byte[] response = new byte[length];
        input.readFully(response);
        return new JSONObject(new String(response, StandardCharsets.UTF_8));
    }

    private String requireAcceptedNodeResult(JSONObject result, String operation) throws Exception {
        requireAllowedFields(
            result,
            setOf(
                "contract_version", "message_type", "request_id", "outcome",
                "reason_code", "session_id", "node_id"
            )
        );
        if (
            !CONTRACT_VERSION.equals(result.optString("contract_version"))
            || !"node.result".equals(result.optString("message_type"))
        ) {
            throw new NodeTransportException("result_identity_invalid");
        }
        if (!"accepted".equals(result.optString("outcome"))) {
            throw new NodeTransportException(requiredString(result, "reason_code", 128));
        }
        String sessionId = requiredIdentifier(result, "session_id");
        if ("session.open".equals(operation) && sessionId == null) {
            throw new NodeTransportException("node_session_missing");
        }
        return sessionId;
    }

    private JSObject parseSyncResult(
        JSONObject result,
        String requestId,
        String nodeSessionId
    ) throws Exception {
        requireExactFields(
            result,
            setOf(
                "contract_version", "message_type", "request_id", "outcome",
                "reason_code", "node_session_id", "schedules"
            )
        );
        if (
            !CONTRACT_VERSION.equals(result.optString("contract_version"))
            || !"reminder.sync.result".equals(result.optString("message_type"))
            || !requestId.equals(result.optString("request_id"))
        ) {
            throw new NodeTransportException("reminder_sync_identity_invalid");
        }
        if (!"accepted".equals(result.optString("outcome"))) {
            throw new NodeTransportException(requiredString(result, "reason_code", 128));
        }
        if (!nodeSessionId.equals(requiredIdentifier(result, "node_session_id"))) {
            throw new NodeTransportException("node_session_mismatch");
        }
        JSONArray schedules = result.getJSONArray("schedules");
        if (schedules.length() > MAX_SCHEDULES) {
            throw new NodeTransportException("reminder_schedule_list_invalid");
        }
        JSArray output = new JSArray();
        Set<String> identities = new HashSet<>();
        for (int index = 0; index < schedules.length(); index++) {
            JSONObject schedule = schedules.getJSONObject(index);
            requireExactFields(schedule, setOf("reminder_id", "fire_at"));
            String reminderId = requiredCanonicalUuid(schedule, "reminder_id");
            String fireAt = requiredOffsetDateTime(schedule, "fire_at");
            String identityKey = reminderId + "\n" + fireAt;
            if (!identities.add(identityKey)) {
                throw new NodeTransportException("reminder_schedule_duplicate");
            }
            output.put(new JSObject().put("reminderId", reminderId).put("fireAt", fireAt));
        }
        return new JSObject()
            .put("mode", "redacted_local_schedule")
            .put("schedules", output);
    }

    private String requiredCanonicalUuid(JSONObject document, String name) throws Exception {
        String value = requiredString(document, name, 64);
        try {
            if (!UUID.fromString(value).toString().equals(value)) {
                throw new NodeTransportException("reminder_id_invalid");
            }
        } catch (IllegalArgumentException error) {
            throw new NodeTransportException("reminder_id_invalid");
        }
        return value;
    }

    private String requiredOffsetDateTime(JSONObject document, String name) throws Exception {
        String value = requiredString(document, name, 80);
        try {
            OffsetDateTime parsed = OffsetDateTime.parse(value);
            if (parsed.getOffset() == null) {
                throw new NodeTransportException("reminder_fire_at_invalid");
            }
            return value;
        } catch (DateTimeParseException error) {
            throw new NodeTransportException("reminder_fire_at_invalid");
        }
    }

    private String requiredIdentifier(JSONObject document, String name) throws Exception {
        String value = requiredString(document, name, 128);
        if (!value.matches("^[a-z0-9][a-z0-9._-]{0,127}$")) {
            throw new NodeTransportException("result_identifier_invalid");
        }
        return value;
    }

    private String requiredString(JSONObject document, String name, int maximum) throws Exception {
        if (!document.has(name) || !(document.get(name) instanceof String)) {
            throw new NodeTransportException("result_string_invalid");
        }
        String value = document.getString(name);
        if (value.length() < 1 || value.length() > maximum || value.indexOf('\0') >= 0) {
            throw new NodeTransportException("result_string_invalid");
        }
        return value;
    }

    private void requireAllowedFields(JSONObject document, Set<String> allowed)
        throws NodeTransportException {
        Set<String> actual = keys(document);
        if (!allowed.containsAll(actual)) {
            throw new NodeTransportException("result_fields_invalid");
        }
    }

    private void requireExactFields(JSONObject document, Set<String> allowed)
        throws NodeTransportException {
        if (!keys(document).equals(allowed)) {
            throw new NodeTransportException("result_fields_invalid");
        }
    }

    private Set<String> keys(JSONObject document) {
        Set<String> values = new HashSet<>();
        Iterator<String> iterator = document.keys();
        while (iterator.hasNext()) {
            values.add(iterator.next());
        }
        return values;
    }

    @SafeVarargs
    private static <T> Set<T> setOf(T... values) {
        return new HashSet<>(Arrays.asList(values));
    }

    private static final class FixedAliasKeyManager extends X509ExtendedKeyManager {
        private final String alias;
        private final PrivateKey privateKey;
        private final X509Certificate[] chain;

        FixedAliasKeyManager(String alias, PrivateKey privateKey, X509Certificate[] chain) {
            this.alias = alias;
            this.privateKey = privateKey;
            this.chain = chain.clone();
        }

        @Override
        public String chooseClientAlias(String[] keyType, Principal[] issuers, java.net.Socket socket) {
            return alias;
        }

        @Override
        public String chooseEngineClientAlias(
            String[] keyType,
            Principal[] issuers,
            javax.net.ssl.SSLEngine engine
        ) {
            return alias;
        }

        @Override
        public String[] getClientAliases(String keyType, Principal[] issuers) {
            return new String[] { alias };
        }

        @Override
        public X509Certificate[] getCertificateChain(String requestedAlias) {
            return alias.equals(requestedAlias) ? chain.clone() : null;
        }

        @Override
        public PrivateKey getPrivateKey(String requestedAlias) {
            return alias.equals(requestedAlias) ? privateKey : null;
        }

        @Override
        public String chooseServerAlias(String keyType, Principal[] issuers, java.net.Socket socket) {
            return null;
        }

        @Override
        public String[] getServerAliases(String keyType, Principal[] issuers) {
            return null;
        }
    }
}
