# src/client.py
# src/client.py
"""
SMTP Client Application.
Interactive CLI for sending emails via the SMTP simulation server.
"""
import socket
import base64
import sys
import config
from typing import Optional

def get_input(prompt: str) -> str:
    return input(prompt).strip()

class SmtpClient:
    def __init__(self, host=config.SMTP_HOST, port=config.SMTP_PORT):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None

    def connect(self):
        try:
            self.sock = socket.create_connection((self.host, self.port))
            response = self.sock.recv(1024).decode()
            print(f"Server: {response.strip()}")
            if not response.startswith("220"):
                raise ConnectionError("Server not ready")
        except socket.error as e:
            print(f"Connection failed: {e}")
            sys.exit(1)

    def send_command(self, cmd: str, arg: str = "") -> str:
        full_cmd = f"{cmd} {arg}\r\n" if arg else f"{cmd}\r\n"
        self.sock.sendall(full_cmd.encode('utf-8'))
        
        # Simple buffer logic for client
        response = self.sock.recv(1024).decode()
        print(f"S: {response.strip()}")
        return response

    def authenticate(self, username, password):
        """
        Performs AUTH PLAIN authentication[cite: 85].
        """
        # \0username\0password
        auth_str = f"\0{username}\0{password}"
        auth_b64 = base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')
        
        self.send_command("AUTH PLAIN")
        # Server should respond with 334 (if standard) or we send immediately depending on flow
        # The project PDF implies a standard flow: 
        # 1. Client: AUTH PLAIN
        # 2. Server: 334 (Request credentials)
        # 3. Client: <Base64 String>
        
        # However, to match the simple server, we might send it in one line or wait.
        # Let's send the base64 string now.
        response = self.send_command(auth_b64)
        if not response.startswith("235"):
            print("Authentication failed!")
            return False
        return True

    def run(self):
        print("=== SMTP Email Client ===")
        self.connect()
        
        try:
            # 1. HELO/EHLO
            self.send_command("EHLO", "client.local")

            # 2. Authentication (Optional in pure SMTP, required by our specs)
            do_auth = get_input("Authenticate? (y/n): ").lower()
            if do_auth == 'y':
                user = get_input("Username: ")
                pw = get_input("Password: ")
                if not self.authenticate(user, pw):
                    return

            # 3. MAIL FROM
            sender = get_input("From: ")
            resp = self.send_command("MAIL FROM:", f"<{sender}>")
            if not resp.startswith("250"): return

            # 4. RCPT TO (Support multiple)
            while True:
                recipient = get_input("To (leave empty to finish): ")
                if not recipient:
                    break
                self.send_command("RCPT TO:", f"<{recipient}>")

            # 5. DATA
            resp = self.send_command("DATA")
            if not resp.startswith("354"): return

            # 6. Message Body
            subject = get_input("Subject: ")
            print("Enter message body (type '.' on a new line to finish):")
            
            # Construct simple MIME headers [cite: 121]
            headers = [
                f"From: {sender}",
                f"Subject: {subject}",
                "MIME-Version: 1.0",
                "Content-Type: text/plain; charset=utf-8",
                "", 
                "" # Empty line between headers and body
            ]
            self.sock.sendall("\r\n".join(headers).encode('utf-8'))

            # Send body lines
            while True:
                line = input()
                if line == ".":
                    self.sock.sendall(b"\r\n.\r\n")
                    break
                # Handle double dot for transparency
                if line.startswith("."):
                    line = "." + line
                self.sock.sendall((line + "\r\n").encode('utf-8'))

            # Receive final response for DATA
            response = self.sock.recv(1024).decode()
            print(f"S: {response.strip()}")

            # 7. QUIT
            self.send_command("QUIT")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            if self.sock:
                self.sock.close()

# if __name__ == "__main__":
#     client = SmtpClient()
#     client.run()
def main():
    client = SmtpClient()
    client.run()

if __name__ == "__main__":
    main()