import base64
from django.conf import settings
from cryptography.fernet import Fernet

def get_fernet() -> Fernet:
    # Derive a 32-byte key from settings.SECRET_KEY
    raw_key = settings.SECRET_KEY.encode("utf-8")
    if len(raw_key) < 32:
        raw_key = raw_key.ljust(32, b"0")
    else:
        raw_key = raw_key[:32]
    
    base64_key = base64.urlsafe_b64encode(raw_key)
    return Fernet(base64_key)

def encrypt_password(password: str) -> str:
    if not password:
        return ""
    fernet = get_fernet()
    return fernet.encrypt(password.encode("utf-8")).decode("utf-8")

def decrypt_password(encrypted_password: str) -> str:
    if not encrypted_password:
        return ""
    fernet = get_fernet()
    return fernet.decrypt(encrypted_password.encode("utf-8")).decode("utf-8")
