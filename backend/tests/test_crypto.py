from app.core import crypto


def test_encrypt_decrypt_roundtrip():
    token = crypto.encrypt("sk-secret-123")
    assert token != "sk-secret-123"
    assert crypto.decrypt(token) == "sk-secret-123"


def test_encrypt_produces_different_tokens():
    assert crypto.encrypt("same") != crypto.encrypt("same")
