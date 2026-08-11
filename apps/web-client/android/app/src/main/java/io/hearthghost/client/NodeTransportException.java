package io.hearthghost.client;

final class NodeTransportException extends Exception {
    private final String reasonCode;

    NodeTransportException(String reasonCode) {
        super(reasonCode);
        this.reasonCode = reasonCode;
    }

    String reasonCode() {
        return reasonCode;
    }
}
