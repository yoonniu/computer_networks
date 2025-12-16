# src/auth.py
# BASE64-encoded authentication following RFC 4954 specifications
# src/auth.py
"""
Authentication module implementing SMTP AUTH PLAIN.
References: RFC 4954
"""
import base64
import binascii
from typing import Tuple, Optional
from logger import log_debug, log_error

# Simulating a user database [cite: 138]
# In a real system, this would be a secure database or hashed file.
USER_DATABASE = {
    "student": "network2025",
    "admin": "admin123",
    "user1": "pass1"
}

class Authenticator:
    @staticmethod
    def validate_plain_auth(base64_string: str) -> Tuple[bool, str]:
        """
        Validates a BASE64 encoded AUTH PLAIN string.
        Format: [authzid] \0 [authcid] \0 [password] [cite: 88]
        """
        try:
            decoded_bytes = base64.b64decode(base64_string)
            decoded_str = decoded_bytes.decode('utf-8')
            
            # Split by null byte
            parts = decoded_str.split('\0')
            
            # The format usually results in 3 parts: [authzid, authcid, password]
            # If authzid is empty, it might start with \0
            if len(parts) < 3:
                return False, "Invalid AUTH format"

            # Depending on implementation, index 1 is usually the username (authcid)
            # and index 2 is the password.
            username = parts[1]
            password = parts[2]

            if username in USER_DATABASE and USER_DATABASE[username] == password:
                return True, "Authentication successful"
            else:
                return False, "Invalid credentials"

        except (binascii.Error, UnicodeDecodeError, IndexError) as e:
            log_error(f"Authentication error: {e}")
            return False, "Decoding failed"