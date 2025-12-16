# src/storage.py
#  file-based mailbox system that stores received messages in a structured format
# src/storage.py
"""
Mail Storage System.
Manages file-based mailbox storage organized by recipient.
"""
import os
import time
import uuid
import config
from logger import log_info, log_error

class MailStorage:
    def __init__(self, storage_dir: str = "mailbox"):
        self.storage_dir = storage_dir
        self._ensure_storage_dir()

    def _ensure_storage_dir(self) -> None:
        """Creates the main mailbox directory if it doesn't exist."""
        if not os.path.exists(self.storage_dir):
            try:
                os.makedirs(self.storage_dir)
            except OSError as e:
                log_error(f"Failed to create storage directory: {e}")

    def save_email(self, recipient: str, sender: str, data: str) -> bool:
        """
        Saves an email to a recipient's specific mailbox folder.
        Uses a unique filename to prevent overwrites[cite: 146].
        """
        # Sanitize recipient email for folder name (basic sanitization)
        safe_recipient = "".join(c for c in recipient if c.isalnum() or c in "._-@")
        user_dir = os.path.join(self.storage_dir, safe_recipient)

        try:
            if not os.path.exists(user_dir):
                os.makedirs(user_dir)

            # Generate unique filename: timestamp_uuid.eml
            filename = f"{int(time.time())}_{uuid.uuid4().hex[:8]}.eml"
            file_path = os.path.join(user_dir, filename)

            with open(file_path, "w", encoding="utf-8") as f:
                # Add a metadata header for easier reading
                f.write(f"X-Sender: {sender}\n")
                f.write(f"X-Recipient: {recipient}\n")
                f.write(f"X-Received: {time.ctime()}\n")
                f.write("-" * 20 + "\n")
                f.write(data)
            
            log_info(f"Email saved for {recipient} at {file_path}")
            return True

        except IOError as e:
            log_error(f"Failed to save email for {recipient}: {e}")
            return False