import cryptography.x509
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from cryptography.hazmat.primitives.asymmetric import padding
import base64
import datetime
from hashlib import sha256
import json
import jwcrypto.jwt, jwcrypto.jwk

# This is the fingerprint of the certificate that signed the JWT we are using from the jagex CDN so we can validate we are trusting the right certificate chain.
JAGEX_PACKAGE_CERTIFICATE_SHA256_HASH = "848bae7e92dc58570db50cdfc933a78204c1b00f05d64f753a307ebbaed2404f"

def validate_and_decode_jwt(jwt):
    # Deserialize the leaf certificate and validate the fingerprint of the certificate
    trust_path = jwt.token.jose_header.get("x5c", [])
    leaf_cert_b64 = trust_path[0]
    leaf_cert_sha256_hash = sha256(leaf_cert_b64.encode('utf8')).hexdigest()

    print("Validating fingerprint of the certificate that signed the JWT...")
    if leaf_cert_sha256_hash != JAGEX_PACKAGE_CERTIFICATE_SHA256_HASH:
        raise Exception("The certificate in the JWT header does not match the expected fingerprint.")

    leaf_cert = cryptography.x509.load_der_x509_certificate(
        base64.b64decode(leaf_cert_b64))

    # Derive public key from the package cert and convert to JWK
    public_key = leaf_cert.public_key()
    public_key = public_key.public_bytes(Encoding.PEM, PublicFormat.PKCS1)
    public_key = jwcrypto.jwk.JWK.from_pem(public_key)

    # Validate JWT and access claims
    jwt.validate(public_key)
    print('''The jwt has validated against the certificate. 
        Issuer: {}
        Subject: {}
        Expiration UTC: {}
        '''.format(leaf_cert.issuer, leaf_cert.subject, leaf_cert.not_valid_after))

    # Build certificate chain
    trust_path = jwt.token.jose_header.get("x5c", [])
    trust_path = [
        cryptography.x509.load_der_x509_certificate(base64.b64decode(cert))
        for cert in trust_path
    ]

    # Verify certificate chain
    for i in range(len(trust_path) - 1):
        issuer_certificate = trust_path[i + 1]
        subject_certificate = trust_path[i]
        issuer_public_key = issuer_certificate.public_key()
        issuer_public_key.verify(
            subject_certificate.signature,
            subject_certificate.tbs_certificate_bytes,
            padding.PKCS1v15(),
            subject_certificate.signature_hash_algorithm,
        )
        # Verify certificate expiration
        current_time = datetime.datetime.utcnow()
        if current_time < issuer_certificate.not_valid_before or current_time > issuer_certificate.not_valid_after:
            raise Exception("Issuer certificate has expired.")

    return json.loads(jwt.claims)
