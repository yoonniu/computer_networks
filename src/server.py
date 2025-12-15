# src/server.py

import socket
import threading
from enum import Enum, auto
from typing import Optional, List, Tuple

import config
from logger import log_info, log_error


# SMTP Session States
class SmtpState(Enum):

    CONNECTED = auto() 
    HELO = auto()       
    AUTH = auto()      
    MAIL = auto()     
    RCPT = auto()       
    DATA = auto()      
    QUIT = auto()     


class SmtpSession:
    
    def __init__(self, client_socket: socket.socket, client_address: Tuple[str, int]):
        self.socket = client_socket
        self.address = client_address
        self.state = SmtpState.CONNECTED

        self.client_hostname: Optional[str] = None
        self.authenticated: bool = False
        self.sender: Optional[str] = None
        self.recipients: List[str] = []
        self.message_data: Optional[str] = None
        
        self.buffer = ""
    
    def send_response(self, code: int, message: str) -> None:
        response = f"{code} {message}\r\n"
        try:
            self.socket.sendall(response.encode("utf-8"))
            log_info(f"[{self.address}] Sent: {code} {message}")
        except socket.error as e:
            log_error(f"[{self.address}] Failed to send response: {e}")
    
    def receive_line(self) -> Optional[str]:
        while "\r\n" not in self.buffer:
            try:
                data = self.socket.recv(config.RECV_BUFFER_SIZE)
                if not data:
                    return None 
                self.buffer += data.decode("utf-8")
            except socket.error as e:
                log_error(f"[{self.address}] Receive error: {e}")
                return None
        
        line, self.buffer = self.buffer.split("\r\n", 1)
        return line
    
    def read_message(self) -> Optional[str]:
        data_lines = []
        while True:
            line = self.receive_line()
            if line is None:
                return None 
            
            # just to check for end of data 
            if line == ".":
                break
            if line.startswith("."):
                line = line[1:]

            data_lines.append(line)
        return "\r\n".join(data_lines)
    
    def handle_ehlo(self, argument: str) -> None:
        if not argument:
            self.send_response(501, "Syntax error: hostname required")
            return
        
        self.client_hostname = argument
        self.state = SmtpState.HELO
        # just to avoid bugs we reset sender recipient and message_data
        self.sender = None
        self.recipients = []
        self.message_data = None
        
        self.send_response(250, f"{config.SERVER_DOMAIN} Hello {argument}")
        log_info(f"[{self.address}] Client identified as: {argument}")
    
    def handle_auth(self, argument: str) -> None:
        if self.state not in (SmtpState.HELO, SmtpState.AUTH):
            self.send_response(503, "Bad sequence of commands")
            return

        if argument.upper().startswith("QUENTIN"):
            self.authenticated = True
            self.state = SmtpState.AUTH
            self.send_response(235, "Authentication successful")
            log_info(f"[{self.address}] Client authenticated")
        else:
            self.send_response(504, "Not authorized")
    
    def handle_mail_from(self, argument: str) -> None:
        if self.state not in (SmtpState.HELO, SmtpState.AUTH):
            self.send_response(503, "Bad sequence of commands")
            return
        
        argument_upper = argument.upper()
        if not argument_upper.startswith("FROM:"):
            self.send_response(501, "Syntax error in MAIL FROM")
            return

        sender = argument[5:].strip()
        if sender.startswith("<") and sender.endswith(">"):
            sender = sender[1:-1]
        
        self.sender = sender
        self.state = SmtpState.MAIL
        self.recipients = [] 
        self.message_data = None
        
        self.send_response(250, "OK")
        log_info(f"[{self.address}] Sender set: {sender}")
    
    def handle_rcpt_to(self, argument: str) -> None:
        if self.state not in (SmtpState.MAIL, SmtpState.RCPT):
            self.send_response(503, "Bad sequence of commands")
            return
        
        argument_upper = argument.upper()
        if not argument_upper.startswith("TO:"):
            self.send_response(501, "Syntax error in RCPT TO")
            return
        
        recipient = argument[3:].strip()
        if recipient.startswith("<") and recipient.endswith(">"):
            recipient = recipient[1:-1]
        
        # secure server for sending an email to 100,000 people 
        if len(self.recipients) >= config.MAX_RECIPIENTS:
            self.send_response(452, "Too many recipients")
            return
        
        self.recipients.append(recipient)
        self.state = SmtpState.RCPT
        
        self.send_response(250, "OK")
        log_info(f"[{self.address}] Recipient added: {recipient}")
    
    def handle_data(self) -> None:
        if self.state != SmtpState.RCPT:
            self.send_response(503, "Bad sequence of commands")
            return
        
        self.send_response(354, "Start mail input; end with <CRLF>.<CRLF>")
        self.state = SmtpState.DATA
        
        message = self.read_message()
        if message is None:
            log_error(f"[{self.address}] Connection lost during DATA")
            return

        self.message_data = message
        
        # TODO: queue the message 
        # TODO: store the message
        
        log_info(f"[{self.address}] Message received: {len(message)} bytes, "
                 f"from {self.sender} to {self.recipients}")
        
        self.state = SmtpState.AUTH if self.authenticated else SmtpState.HELO
        self.sender = None
        self.recipients = []
        
        self.send_response(250, "OK: Message accepted for delivery")
    
    def handle_reset(self) -> None:
        if self.state == SmtpState.CONNECTED:
            self.send_response(503, "Bad sequence of commands")
            return

        self.sender = None
        self.recipients = []
        self.message_data = None

        if self.authenticated:
            self.state = SmtpState.AUTH
        else:
            self.state = SmtpState.HELO
        
        self.send_response(250, "OK")
        log_info(f"[{self.address}] Transaction reset")
    
    def handle_noop(self) -> None:
        self.send_response(250, "OK")
    
    def handle_quit(self) -> None:
        self.state = SmtpState.QUIT
        self.send_response(221, f"{config.SERVER_DOMAIN} Service closing transmission channel")
        log_info(f"[{self.address}] Client quit")
    
    def parse_command(self, line: str) -> Tuple[str, str]:
        parts = line.split(None, 1)  
        command = parts[0].upper() if parts else ""
        argument = parts[1] if len(parts) > 1 else ""
        return command, argument
    
    def handle_command(self, line: str) -> bool:
        command, argument = self.parse_command(line)
        log_info(f"[{self.address}] Received: {command} {argument}")

        if command in ("EHLO", "HELO"):
            self.handle_ehlo(argument)
        elif command == "AUTH":
            self.handle_auth(argument)
        elif command == "MAIL":
            self.handle_mail_from(argument)
        elif command == "RCPT":
            self.handle_rcpt_to(argument)
        elif command == "DATA":
            self.handle_data()
        elif command == "RSET":
            self.handle_reset()
        elif command == "NOOP":
            self.handle_noop()
        elif command == "QUIT":
            self.handle_quit()
            return False  
        else:
            self.send_response(500, "Command not recognized")
        
        return True 
    
    def run(self) -> None:
        log_info(f"[{self.address}] New connection")
        try:
            self.socket.settimeout(config.CONNECTION_TIMEOUT)
            self.send_response(220, f"{config.SERVER_DOMAIN} SMTP Service Ready")

            while self.state != SmtpState.QUIT:
                line = self.receive_line()
                if line is None:
                    log_info(f"[{self.address}] Connection closed by client")
                    break
                if not line.strip():
                    continue  
                cmd=self.handle_command(line)
                if not cmd:
                    break  

        except socket.timeout:
            log_info(f"[{self.address}] Connection timed out")
            self.send_response(421, "Connection timed out")
        except Exception as e:
            log_error(f"[{self.address}] Session error: {e}")
        
        finally:
            try:
                self.socket.close()
            except socket.error:
                pass
            log_info(f"[{self.address}] Connection closed")



# SMTP Server
class SmtpServer:
    
    def __init__(self, host: str = config.SMTP_HOST, port: int = config.SMTP_PORT):
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False
    
    def start(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM) # AF_INET=ipv4 and SOCK_STREAM=UDP
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(config.MAX_CLIENTS)
            self.running = True
            
            log_info(f"SMTP server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, client_address = self.socket.accept()  
                    session = SmtpSession(client_socket, client_address)
                    thread = threading.Thread(target=session.run, daemon=True)
                    thread.start()
                    log_info(f"Spawned thread for client {client_address}")
                
                except socket.error as e:
                    if self.running:
                        log_error(f"Accept error: {e}")
        
        except socket.error as e:
            log_error(f"Server socket error: {e}")
        
        finally:
            self.stop()
    
    def stop(self) -> None:
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except socket.error:
                pass
            self.socket = None
        log_info("SMTP server stopped")



# Main Entry Point

def main():
    server = SmtpServer()
    try:
        server.start()
    except KeyboardInterrupt:
        log_info("Received shutdown signal")
        server.stop()


if __name__ == "__main__":
    main()