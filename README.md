# SMTP Email Communication Simulation System

This project is a **command-line based SMTP email simulation system** implemented in Python using low-level socket programming.
It demonstrates how email transmission works at the application layer by implementing the SMTP protocol without relying on
high-level email libraries such as `smtplib`.

The system is designed for educational purposes and follows the concepts taught in computer networking courses,
including protocol design, state machines, concurrency, and client-server communication.

---

## Features

### SMTP Server
- TCP socket-based SMTP server
- Multi-threaded client handling (one thread per connection)
- SMTP command support:
  - `EHLO` / `HELO`
  - `AUTH PLAIN` (Base64 authentication)
  - `MAIL FROM`
  - `RCPT TO` (multiple recipients supported)
  - `DATA`
  - `QUIT`
- Proper SMTP response codes (`220`, `250`, `354`, `503`, `500`, etc.)
- Strict command sequence enforcement using a state machine
- Logging of all SMTP transactions

### Message Queue
- Decouples message reception from delivery
- Persistent queue storage using JSON
- Retry logic hooks for failed deliveries (simulation)

### Mail Storage
- File-based mailbox system
- Messages stored per recipient in `.eml` format

### SMTP Client (CLI)
- Interactive command-line interface
- Socket-based SMTP implementation (no `smtplib`)
- Supports authentication, error handling, and full SMTP transaction flow

---

## Project Structure

