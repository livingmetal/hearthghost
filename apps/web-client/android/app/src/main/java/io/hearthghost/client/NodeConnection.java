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

final class NodeConnection {
    private static final String HOST = "192.168.55.100";
    private static final int PORT = 38443;
    private static final String CONTRACT_VERSION = "1.0";
    private static final String ALPN = "hearthghost-node/1";
    private static final int CONNECT_TIMEOUT_MILLIS = 5_000;
    private static final int SOCKET_TIMEOUT_MILLIS = 20_000;
    private static final int MAX_FRAME_BYTES = 16 * 1024;
    private static final int MAX_TEXT_LENGTH = 4_000;
    private static final int MAX_RESPONSE_TEXT_LENGTH = 8_000;
    private static final int MAX_CHARACTER_NAME_LENGTH = 80;
    private static final int MAX_EVENTS = 8;
    private static final int MAX_PROPOSALS = 8;

    private final NodeIdentityStore identity;
    private SSLSocket socket;
    private DataInputStream input;
    private DataOutputStream output;
    private String nodeSessionId;
    private String conversationSessionId;
    private long nextSequence;

    NodeConnection(NodeIdentityStore identity) {
        this.identity = identity;
    }

    JSObject connect() throws Exception {
        disconnect();
        NodeIdentityStore.IdentityStatus status = identity.status();
        if (!status.keyPresent || !status.certificateInstalled || !status.nonExportable) {
            throw new NodeTransportException("node_identity_not_provisioned");
        }

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
        SSLSocket candidate = (SSLSocket) context.getSocketFactory().createSocket();
        try {
            candidate.setUseClientMode(true);
            candidate.setEnabledProtocols(new String[] { "TLSv1.3" });
            SSLParameters parameters = candidate.getSSLParameters();
            parameters.setEndpointIdentificationAlgorithm("HTTPS");
            parameters.setApplicationProtocols(new String[] { ALPN });
            candidate.setSSLParameters(parameters);
            candidate.connect(new InetSocketAddress(HOST, PORT), CONNECT_TIMEOUT_MILLIS);
            candidate.setSoTimeout(SOCKET_TIMEOUT_MILLIS);
            candidate.startHandshake();
            if (
                !"TLSv1.3".equals(candidate.getSession().getProtocol())
                || !ALPN.equals(candidate.getApplicationProtocol())
                || candidate.getSession().getPeerCertificates().length == 0
            ) {
                throw new NodeTransportException("tls_profile_not_negotiated");
            }
            socket = candidate;
            input = new DataInputStream(candidate.getInputStream());
            output = new DataOutputStream(candidate.getOutputStream());
            GatewayResult opened = gatewayExchange(
                new JSONObject()
                    .put("contract_version", CONTRACT_VERSION)
                    .put("message_type", "session.open")
                    .put("request_id", UUID.randomUUID().toString())
                    .put("node_id", NodeIdentityStore.NODE_ID)
            );
            if (!opened.accepted || opened.sessionId == null) {
                throw new NodeTransportException(opened.reasonCode);
            }
            nodeSessionId = opened.sessionId;
            nextSequence = 1;
            GatewayResult capability = gatewayExchange(
                new JSONObject()
                    .put("contract_version", CONTRACT_VERSION)
                    .put("message_type", "capability.request")
                    .put("request_id", UUID.randomUUID().toString())
                    .put("session_id", nodeSessionId)
                    .put("sequence", consumeSequence())
                    .put("capability", "conversation.text")
            );
            String trust;
            JSArray grants = new JSArray();
            if (capability.accepted) {
                trust = "trusted";
                grants.put("conversation.text");
            } else if ("node_not_trusted".equals(capability.reasonCode)) {
                trust = "untrusted";
            } else if (
                "capability_not_granted".equals(capability.reasonCode)
                || "capability_not_advertised".equals(capability.reasonCode)
            ) {
                trust = "trusted";
            } else {
                throw new NodeTransportException(capability.reasonCode);
            }
            return new JSObject()
                .put("authenticated", true)
                .put("nodeId", NodeIdentityStore.NODE_ID)
                .put("technicalSessionId", nodeSessionId)
                .put("trust", trust)
                .put("grantedCapabilities", grants);
        } catch (Exception error) {
            closeSocket(candidate);
            clearState();
            throw error;
        }
    }

    JSObject openConversation(String requestedNodeSessionId) throws Exception {
        requireConnected();
        if (!nodeSessionId.equals(requestedNodeSessionId)) {
            throw new NodeTransportException("node_session_mismatch");
        }
        JSONObject result = conversationExchange(
            new JSONObject()
                .put("contract_version", CONTRACT_VERSION)
                .put("message_type", "conversation.open")
                .put("request_id", UUID.randomUUID().toString())
                .put("node_session_id", nodeSessionId)
                .put("sequence", consumeSequence())
        );
        conversationSessionId = requiredIdentifier(result, "conversation_session_id");
        return conversationOutput(result, false);
    }

    JSObject sendText(String requestedConversationSessionId, String text) throws Exception {
        requireConversation(requestedConversationSessionId);
        if (
            text == null
            || text.length() < 1
            || text.length() > MAX_TEXT_LENGTH
            || text.indexOf('\0') >= 0
        ) {
            throw new NodeTransportException("text_input_invalid");
        }
        JSONObject result = conversationExchange(
            new JSONObject()
                .put("contract_version", CONTRACT_VERSION)
                .put("message_type", "conversation.text")
                .put("request_id", UUID.randomUUID().toString())
                .put("node_session_id", nodeSessionId)
                .put("sequence", consumeSequence())
                .put("conversation_session_id", conversationSessionId)
                .put("text", text)
        );
        String response = requiredBoundedString(
            result,
            "response_text",
            MAX_RESPONSE_TEXT_LENGTH
        );
        return conversationOutput(result, true).put("responseText", response);
    }

    JSObject closeConversation(String requestedConversationSessionId) throws Exception {
        requireConversation(requestedConversationSessionId);
        JSONObject result = conversationExchange(
            new JSONObject()
                .put("contract_version", CONTRACT_VERSION)
                .put("message_type", "conversation.close")
                .put("request_id", UUID.randomUUID().toString())
                .put("node_session_id", nodeSessionId)
                .put("sequence", consumeSequence())
                .put("conversation_session_id", conversationSessionId)
        );
        JSObject output = conversationOutput(result, false);
        conversationSessionId = null;
        return output;
    }

    void disconnect() {
        if (socket == null) {
            clearState();
            return;
        }
        if (conversationSessionId != null) {
            try {
                closeConversation(conversationSessionId);
            } catch (Exception ignored) {
                // One bounded best-effort close only; the socket is always closed below.
            }
        }
        if (nodeSessionId != null) {
            try {
                gatewayExchange(
                    new JSONObject()
                        .put("contract_version", CONTRACT_VERSION)
                        .put("message_type", "session.close")
                        .put("request_id", UUID.randomUUID().toString())
                        .put("session_id", nodeSessionId)
                );
            } catch (Exception ignored) {
                // No retry. Closing the transport invalidates the client binding.
            }
        }
        closeSocket(socket);
        clearState();
    }

    private GatewayResult gatewayExchange(JSONObject request) throws Exception {
        String requestId = request.getString("request_id");
        JSONObject result = exchange(request);
        requireExactFields(
            result,
            setOf(
                "contract_version",
                "message_type",
                "request_id",
                "outcome",
                "reason_code",
                "session_id",
                "node_id"
            ),
            false
        );
        requireCommonResult(result, requestId, "node.result");
        String sessionId = optionalIdentifier(result, "session_id");
        optionalIdentifier(result, "node_id");
        return new GatewayResult(
            "accepted".equals(result.getString("outcome")),
            requiredBoundedString(result, "reason_code", 128),
            sessionId
        );
    }

    private JSONObject conversationExchange(JSONObject request) throws Exception {
        String requestId = request.getString("request_id");
        JSONObject result = exchange(request);
        requireExactFields(
            result,
            setOf(
                "contract_version",
                "message_type",
                "request_id",
                "outcome",
                "reason_code",
                "node_session_id",
                "conversation_session_id",
                "response_text",
                "events",
                "proposed_actions",
                "character_profile"
            ),
            false
        );
        requireCommonResult(result, requestId, "conversation.result");
        if (!"accepted".equals(result.getString("outcome"))) {
            throw new NodeTransportException(
                requiredBoundedString(result, "reason_code", 128)
            );
        }
        optionalIdentifier(result, "node_session_id");
        optionalIdentifier(result, "conversation_session_id");
        if (result.has("response_text")) {
            requiredBoundedString(result, "response_text", MAX_RESPONSE_TEXT_LENGTH);
        }
        if (!result.has("character_profile")) {
            throw new NodeTransportException("character_profile_missing");
        }
        validatedCharacterProfileOutput(result.getJSONObject("character_profile"));
        validateEvents(result.optJSONArray("events"));
        validateProposals(result.optJSONArray("proposed_actions"));
        return result;
    }

    private JSONObject exchange(JSONObject request) throws Exception {
        requireConnectedStreams();
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

    private JSObject conversationOutput(JSONObject result, boolean includeResponse)
        throws Exception {
        String conversationId = requiredIdentifier(result, "conversation_session_id");
        JSObject output = new JSObject()
            .put("conversationSessionId", conversationId)
            .put("events", validatedEventsOutput(result.optJSONArray("events")))
            .put(
                "characterProfile",
                validatedCharacterProfileOutput(result.getJSONObject("character_profile"))
            );
        String resultNodeSession = optionalIdentifier(result, "node_session_id");
        if (resultNodeSession != null) {
            output.put("nodeSessionId", resultNodeSession);
        }
        if (includeResponse) {
            output.put(
                "responseText",
                requiredBoundedString(result, "response_text", MAX_RESPONSE_TEXT_LENGTH)
            );
        }
        return output;
    }

    private JSObject validatedCharacterProfileOutput(JSONObject profile) throws Exception {
        requireExactFields(profile, setOf("name"), true);
        String name = requiredBoundedString(profile, "name", MAX_CHARACTER_NAME_LENGTH);
        if (!name.equals(name.trim()) || hasUnsupportedCharacterNameCodePoint(name)) {
            throw new NodeTransportException("character_profile_invalid");
        }
        return new JSObject().put("name", name);
    }

    private boolean hasUnsupportedCharacterNameCodePoint(String value) {
        for (int offset = 0; offset < value.length();) {
            int codePoint = value.codePointAt(offset);
            int type = Character.getType(codePoint);
            if (
                type == Character.CONTROL
                || type == Character.FORMAT
                || type == Character.SURROGATE
                || type == Character.PRIVATE_USE
                || type == Character.UNASSIGNED
            ) {
                return true;
            }
            offset += Character.charCount(codePoint);
        }
        return false;
    }

    private void requireCommonResult(
        JSONObject result,
        String requestId,
        String messageType
    ) throws Exception {
        if (
            !CONTRACT_VERSION.equals(result.optString("contract_version"))
            || !messageType.equals(result.optString("message_type"))
            || !requestId.equals(result.optString("request_id"))
            || (
                !"accepted".equals(result.optString("outcome"))
                && !"denied".equals(result.optString("outcome"))
            )
        ) {
            throw new NodeTransportException("result_identity_invalid");
        }
        requiredBoundedString(result, "reason_code", 128);
    }

    private JSArray validatedEventsOutput(JSONArray events) throws Exception {
        validateEvents(events);
        JSArray output = new JSArray();
        if (events == null) {
            return output;
        }
        for (int index = 0; index < events.length(); index++) {
            JSONObject event = events.getJSONObject(index);
            JSObject semantic = new JSObject();
            semantic.put("type", "character.state");
            semantic.put(
                "payload",
                new JSObject().put(
                    "state",
                    event.getJSONObject("payload").getString("state")
                )
            );
            output.put(semantic);
        }
        return output;
    }

    private void validateEvents(JSONArray events) throws Exception {
        if (events == null) {
            return;
        }
        if (events.length() > MAX_EVENTS) {
            throw new NodeTransportException("semantic_event_list_invalid");
        }
        Set<String> states = setOf(
            "sleeping",
            "listening",
            "thinking",
            "speaking",
            "engaged"
        );
        for (int index = 0; index < events.length(); index++) {
            JSONObject event = events.getJSONObject(index);
            requireExactFields(event, setOf("type", "payload"), true);
            JSONObject payload = event.getJSONObject("payload");
            requireExactFields(payload, setOf("state"), true);
            if (
                !"character.state".equals(event.getString("type"))
                || !states.contains(payload.getString("state"))
            ) {
                throw new NodeTransportException("semantic_event_invalid");
            }
        }
    }

    private void validateProposals(JSONArray proposals) throws Exception {
        if (proposals == null) {
            return;
        }
        if (proposals.length() > MAX_PROPOSALS) {
            throw new NodeTransportException("proposal_list_invalid");
        }
        for (int index = 0; index < proposals.length(); index++) {
            JSONObject proposal = proposals.getJSONObject(index);
            requireExactFields(
                proposal,
                setOf(
                    "name",
                    "arguments",
                    "authorization_status",
                    "execution_status"
                ),
                true
            );
            if (
                !proposal.getString("name").matches(
                    "^[a-z][a-z0-9_-]{0,63}(\\.[a-z][a-z0-9_-]{0,63})+$"
                )
                || !"pending_policy".equals(
                    proposal.getString("authorization_status")
                )
                || !"not_executed".equals(proposal.getString("execution_status"))
            ) {
                throw new NodeTransportException("proposal_authority_invalid");
            }
            JSONObject arguments = proposal.getJSONObject("arguments");
            Iterator<String> keys = arguments.keys();
            while (keys.hasNext()) {
                String key = keys.next();
                Object value = arguments.get(key);
                if (
                    key.length() > 128
                    || !(value instanceof String)
                    || ((String) value).length() > 256
                ) {
                    throw new NodeTransportException("proposal_arguments_invalid");
                }
            }
        }
    }

    private void requireExactFields(
        JSONObject document,
        Set<String> allowed,
        boolean exact
    ) throws NodeTransportException {
        Set<String> actual = new HashSet<>();
        Iterator<String> keys = document.keys();
        while (keys.hasNext()) {
            actual.add(keys.next());
        }
        if ((exact && !actual.equals(allowed)) || (!exact && !allowed.containsAll(actual))) {
            throw new NodeTransportException("result_fields_invalid");
        }
    }

    private String requiredIdentifier(JSONObject document, String name) throws Exception {
        String value = requiredBoundedString(document, name, 128);
        if (!value.matches("^[a-z0-9][a-z0-9._-]{0,127}$")) {
            throw new NodeTransportException("result_identifier_invalid");
        }
        return value;
    }

    private String optionalIdentifier(JSONObject document, String name) throws Exception {
        if (!document.has(name)) {
            return null;
        }
        return requiredIdentifier(document, name);
    }

    private String requiredBoundedString(
        JSONObject document,
        String name,
        int maximum
    ) throws Exception {
        if (!document.has(name) || !(document.get(name) instanceof String)) {
            throw new NodeTransportException("result_string_invalid");
        }
        String value = document.getString(name);
        if (value.length() < 1 || value.length() > maximum) {
            throw new NodeTransportException("result_string_invalid");
        }
        return value;
    }

    private long consumeSequence() throws NodeTransportException {
        if (nextSequence < 1 || nextSequence == Long.MAX_VALUE) {
            throw new NodeTransportException("sequence_exhausted");
        }
        return nextSequence++;
    }

    private void requireConnected() throws NodeTransportException {
        requireConnectedStreams();
        if (nodeSessionId == null) {
            throw new NodeTransportException("node_session_not_open");
        }
    }

    private void requireConnectedStreams() throws NodeTransportException {
        if (socket == null || input == null || output == null || socket.isClosed()) {
            throw new NodeTransportException("secure_transport_not_connected");
        }
    }

    private void requireConversation(String requested) throws NodeTransportException {
        requireConnected();
        if (conversationSessionId == null || !conversationSessionId.equals(requested)) {
            throw new NodeTransportException("conversation_session_mismatch");
        }
    }

    private void clearState() {
        socket = null;
        input = null;
        output = null;
        nodeSessionId = null;
        conversationSessionId = null;
        nextSequence = 0;
    }

    private static void closeSocket(SSLSocket value) {
        if (value == null) {
            return;
        }
        try {
            value.close();
        } catch (Exception ignored) {
            // Closing a failed channel is terminal; there is no retry loop.
        }
    }

    @SafeVarargs
    private static <T> Set<T> setOf(T... values) {
        return new HashSet<>(Arrays.asList(values));
    }

    private static final class GatewayResult {
        final boolean accepted;
        final String reasonCode;
        final String sessionId;

        GatewayResult(boolean accepted, String reasonCode, String sessionId) {
            this.accepted = accepted;
            this.reasonCode = reasonCode;
            this.sessionId = sessionId;
        }
    }

    private static final class FixedAliasKeyManager extends X509ExtendedKeyManager {
        private final String alias;
        private final PrivateKey privateKey;
        private final X509Certificate[] chain;

        FixedAliasKeyManager(
            String alias,
            PrivateKey privateKey,
            X509Certificate[] chain
        ) {
            this.alias = alias;
            this.privateKey = privateKey;
            this.chain = chain.clone();
        }

        @Override
        public String chooseClientAlias(
            String[] keyType,
            Principal[] issuers,
            java.net.Socket socket
        ) {
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
        public String chooseServerAlias(
            String keyType,
            Principal[] issuers,
            java.net.Socket socket
        ) {
            return null;
        }

        @Override
        public String[] getServerAliases(String keyType, Principal[] issuers) {
            return null;
        }
    }
}
