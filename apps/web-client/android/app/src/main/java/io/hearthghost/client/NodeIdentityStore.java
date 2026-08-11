package io.hearthghost.client;

import android.content.Context;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;

import org.bouncycastle.operator.ContentSigner;
import org.bouncycastle.operator.jcajce.JcaContentSignerBuilder;
import org.bouncycastle.pkcs.PKCS10CertificationRequest;
import org.bouncycastle.pkcs.jcajce.JcaPKCS10CertificationRequestBuilder;

import java.io.ByteArrayInputStream;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.security.MessageDigest;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.cert.Certificate;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;
import java.security.spec.ECGenParameterSpec;
import java.util.Collection;
import java.util.Date;
import java.util.List;
import java.util.Locale;

import javax.security.auth.x500.X500Principal;

final class NodeIdentityStore {
    static final String NODE_ID = "android-development-01";
    static final String CREDENTIAL_REFERENCE = "hearthghost.android.development.01";
    static final String KEY_ALIAS = "hearthghost.android.development.01.key";
    private static final String KEYSTORE = "AndroidKeyStore";
    private static final String AUTHORITY_FILE = "hearthghost-development-ca.crt";
    private static final int MAX_CERTIFICATE_PEM_LENGTH = 16 * 1024;
    private static final String CLIENT_AUTH_OID = "1.3.6.1.5.5.7.3.2";
    private static final String EXPECTED_NODE_URI =
        "urn:hearthghost:node:" + NODE_ID;

    private final Context context;

    NodeIdentityStore(Context context) {
        this.context = context.getApplicationContext();
    }

    IdentityStatus status() throws Exception {
        KeyStore keyStore = loadKeyStore();
        if (!keyStore.isKeyEntry(KEY_ALIAS)) {
            return new IdentityStatus(false, false, false);
        }
        PrivateKey privateKey = (PrivateKey) keyStore.getKey(KEY_ALIAS, null);
        Certificate[] chain = keyStore.getCertificateChain(KEY_ALIAS);
        boolean installed = chain != null && chain.length >= 2 && authorityFileExists();
        return new IdentityStatus(true, installed, privateKey.getEncoded() == null);
    }

    EnrollmentRequest createEnrollmentRequest() throws Exception {
        KeyPair keyPair = loadOrCreateKeyPair();
        if (keyPair.getPrivate().getEncoded() != null) {
            throw new NodeTransportException("keystore_key_exportable");
        }
        JcaPKCS10CertificationRequestBuilder builder =
            new JcaPKCS10CertificationRequestBuilder(
                new X500Principal("CN=HearthGhost Android Development Node"),
                keyPair.getPublic()
            );
        ContentSigner signer = new JcaContentSignerBuilder("SHA256withECDSA")
            .build(keyPair.getPrivate());
        PKCS10CertificationRequest request = builder.build(signer);
        byte[] encoded = request.getEncoded();
        return new EnrollmentRequest(
            pem("CERTIFICATE REQUEST", encoded),
            hex(MessageDigest.getInstance("SHA-256").digest(encoded))
        );
    }

    IdentityStatus installCertificateChain(
        String nodeCertificatePem,
        String authorityCertificatePem
    ) throws Exception {
        requireBoundedPem(nodeCertificatePem);
        requireBoundedPem(authorityCertificatePem);
        KeyStore keyStore = loadKeyStore();
        if (!keyStore.isKeyEntry(KEY_ALIAS)) {
            throw new NodeTransportException("keystore_key_missing");
        }
        PrivateKey privateKey = (PrivateKey) keyStore.getKey(KEY_ALIAS, null);
        if (privateKey == null || privateKey.getEncoded() != null) {
            throw new NodeTransportException("keystore_key_not_non_exportable");
        }
        X509Certificate current = (X509Certificate) keyStore.getCertificate(KEY_ALIAS);
        X509Certificate node = parseCertificate(nodeCertificatePem);
        X509Certificate authority = parseCertificate(authorityCertificatePem);
        validateChain(current.getPublicKey(), node, authority);
        keyStore.setKeyEntry(
            KEY_ALIAS,
            privateKey,
            null,
            new Certificate[] { node, authority }
        );
        try (FileOutputStream output = context.openFileOutput(
            AUTHORITY_FILE,
            Context.MODE_PRIVATE
        )) {
            output.write(authority.getEncoded());
        }
        return status();
    }

    PrivateKey privateKey() throws Exception {
        KeyStore keyStore = loadKeyStore();
        PrivateKey key = (PrivateKey) keyStore.getKey(KEY_ALIAS, null);
        if (key == null || key.getEncoded() != null) {
            throw new NodeTransportException("non_exportable_key_unavailable");
        }
        return key;
    }

    X509Certificate[] certificateChain() throws Exception {
        Certificate[] certificates = loadKeyStore().getCertificateChain(KEY_ALIAS);
        if (certificates == null || certificates.length < 2) {
            throw new NodeTransportException("node_certificate_not_installed");
        }
        X509Certificate[] chain = new X509Certificate[certificates.length];
        for (int index = 0; index < certificates.length; index++) {
            if (!(certificates[index] instanceof X509Certificate)) {
                throw new NodeTransportException("node_certificate_chain_invalid");
            }
            chain[index] = (X509Certificate) certificates[index];
        }
        return chain;
    }

    X509Certificate authorityCertificate() throws Exception {
        try (FileInputStream input = context.openFileInput(AUTHORITY_FILE)) {
            CertificateFactory factory = CertificateFactory.getInstance("X.509");
            Certificate certificate = factory.generateCertificate(input);
            if (!(certificate instanceof X509Certificate)) {
                throw new NodeTransportException("authority_certificate_invalid");
            }
            return (X509Certificate) certificate;
        }
    }

    private KeyPair loadOrCreateKeyPair() throws Exception {
        KeyStore keyStore = loadKeyStore();
        if (keyStore.isKeyEntry(KEY_ALIAS)) {
            return new KeyPair(
                keyStore.getCertificate(KEY_ALIAS).getPublicKey(),
                (PrivateKey) keyStore.getKey(KEY_ALIAS, null)
            );
        }
        Date now = new Date();
        Date end = new Date(now.getTime() + 10L * 365 * 24 * 60 * 60 * 1000);
        KeyPairGenerator generator = KeyPairGenerator.getInstance(
            KeyProperties.KEY_ALGORITHM_EC,
            KEYSTORE
        );
        generator.initialize(
            new KeyGenParameterSpec.Builder(
                KEY_ALIAS,
                KeyProperties.PURPOSE_SIGN | KeyProperties.PURPOSE_VERIFY
            )
                .setAlgorithmParameterSpec(new ECGenParameterSpec("secp256r1"))
                .setDigests(KeyProperties.DIGEST_SHA256)
                .setCertificateSubject(
                    new X500Principal("CN=HearthGhost Android Development Node")
                )
                .setCertificateSerialNumber(new BigInteger(159, new java.security.SecureRandom()))
                .setCertificateNotBefore(new Date(now.getTime() - 60_000))
                .setCertificateNotAfter(end)
                .setUserAuthenticationRequired(false)
                .build()
        );
        return generator.generateKeyPair();
    }

    private KeyStore loadKeyStore() throws Exception {
        KeyStore keyStore = KeyStore.getInstance(KEYSTORE);
        keyStore.load(null);
        return keyStore;
    }

    private void validateChain(
        PublicKey expectedPublicKey,
        X509Certificate node,
        X509Certificate authority
    ) throws Exception {
        node.checkValidity();
        authority.checkValidity();
        if (!MessageDigest.isEqual(
            expectedPublicKey.getEncoded(),
            node.getPublicKey().getEncoded()
        )) {
            throw new NodeTransportException("node_certificate_key_mismatch");
        }
        if (authority.getBasicConstraints() < 0) {
            throw new NodeTransportException("authority_certificate_not_ca");
        }
        authority.verify(authority.getPublicKey());
        node.verify(authority.getPublicKey());
        List<String> extendedUsage = node.getExtendedKeyUsage();
        if (extendedUsage == null || !extendedUsage.contains(CLIENT_AUTH_OID)) {
            throw new NodeTransportException("node_certificate_missing_client_auth");
        }
        boolean[] keyUsage = node.getKeyUsage();
        if (keyUsage == null || keyUsage.length == 0 || !keyUsage[0]) {
            throw new NodeTransportException("node_certificate_missing_digital_signature");
        }
        if (!hasExpectedNodeUri(node)) {
            throw new NodeTransportException("node_certificate_identity_mismatch");
        }
    }

    private boolean hasExpectedNodeUri(X509Certificate certificate) throws Exception {
        Collection<List<?>> names = certificate.getSubjectAlternativeNames();
        if (names == null) {
            return false;
        }
        for (List<?> name : names) {
            if (
                name.size() == 2
                && Integer.valueOf(6).equals(name.get(0))
                && EXPECTED_NODE_URI.equals(name.get(1))
            ) {
                return true;
            }
        }
        return false;
    }

    private X509Certificate parseCertificate(String pem) throws Exception {
        CertificateFactory factory = CertificateFactory.getInstance("X.509");
        Certificate certificate = factory.generateCertificate(
            new ByteArrayInputStream(pem.getBytes(StandardCharsets.US_ASCII))
        );
        if (!(certificate instanceof X509Certificate)) {
            throw new NodeTransportException("certificate_not_x509");
        }
        return (X509Certificate) certificate;
    }

    private void requireBoundedPem(String value) throws NodeTransportException {
        if (
            value == null
            || value.length() < 1
            || value.length() > MAX_CERTIFICATE_PEM_LENGTH
            || !value.startsWith("-----BEGIN CERTIFICATE-----")
        ) {
            throw new NodeTransportException("certificate_pem_invalid");
        }
    }

    private boolean authorityFileExists() {
        return context.getFileStreamPath(AUTHORITY_FILE).isFile();
    }

    private static String pem(String type, byte[] encoded) {
        String base64 = Base64.encodeToString(encoded, Base64.NO_WRAP);
        StringBuilder output = new StringBuilder();
        output.append("-----BEGIN ").append(type).append("-----\n");
        for (int offset = 0; offset < base64.length(); offset += 64) {
            output.append(base64, offset, Math.min(offset + 64, base64.length()))
                .append('\n');
        }
        output.append("-----END ").append(type).append("-----\n");
        return output.toString();
    }

    private static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            result.append(String.format(Locale.ROOT, "%02x", value & 0xff));
        }
        return result.toString();
    }

    static final class IdentityStatus {
        final boolean keyPresent;
        final boolean certificateInstalled;
        final boolean nonExportable;

        IdentityStatus(
            boolean keyPresent,
            boolean certificateInstalled,
            boolean nonExportable
        ) {
            this.keyPresent = keyPresent;
            this.certificateInstalled = certificateInstalled;
            this.nonExportable = nonExportable;
        }
    }

    static final class EnrollmentRequest {
        final String pem;
        final String sha256;

        EnrollmentRequest(String pem, String sha256) {
            this.pem = pem;
            this.sha256 = sha256;
        }
    }
}
