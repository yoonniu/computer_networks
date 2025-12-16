# src/queue.py
# src/queue.py
"""
Message Queue and Delivery System.
Implements a priority queue with retry logic and JSON persistence.
"""
import heapq
import threading
import time
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Optional
from logger import log_info, log_error, log_debug
from storage import MailStorage

# Retry intervals in seconds (1m, 5m, 15m...) [cite: 110]
RETRY_INTERVALS = [60, 300, 900, 3600, 14400]

@dataclass(order=True)
class QueueItem:
    """
    Represents an item in the priority queue.
    The order is determined by 'delivery_time', ensuring the heap 
    processes the earliest scheduled tasks first[cite: 142].
    """
    delivery_time: float
    priority: int # 1 (High) to 5 (Low) [cite: 143]
    sender: str
    recipient: str
    data: str
    attempts: int = 0

    def to_dict(self):
        return asdict(self)

class MessageQueue:
    def __init__(self, persistence_file="queue_dump.json"):
        self.queue = []
        self.lock = threading.Lock() # Protects queue operations [cite: 145]
        self.persistence_file = persistence_file
        self.storage = MailStorage()
        self.running = False
        self._load_from_disk()

    def enqueue(self, sender: str, recipients: List[str], data: str, priority: int = 3) -> None:
        """Adds a message to the queue for each recipient."""
        with self.lock:
            for recipient in recipients:
                item = QueueItem(
                    delivery_time=time.time(),
                    priority=priority,
                    sender=sender,
                    recipient=recipient,
                    data=data
                )
                heapq.heappush(self.queue, item)
            
            log_info(f"Enqueued message for {len(recipients)} recipients")
            self._save_to_disk()

    def start_worker(self):
        """Starts the background processing thread."""
        self.running = True
        worker_thread = threading.Thread(target=self._process_queue, daemon=True)
        worker_thread.start()
        log_info("Queue worker thread started")

    def stop_worker(self):
        self.running = False

    def _process_queue(self):
        """
        Main loop handling message delivery.
        Checks heap for messages ready to be delivered.
        """
        while self.running:
            item_to_process = None
            
            with self.lock:
                if self.queue:
                    # Check if the top item is ready for delivery (time <= now)
                    if self.queue[0].delivery_time <= time.time():
                        item_to_process = heapq.heappop(self.queue)
            
            if item_to_process:
                self._attempt_delivery(item_to_process)
            else:
                time.sleep(1) # Prevent busy waiting

    def _attempt_delivery(self, item: QueueItem):
        """
        Tries to deliver the message (save to storage).
        If fails, schedules retry using exponential backoff[cite: 109].
        """
        success = self.storage.save_email(item.recipient, item.sender, item.data)
        
        if success:
            log_debug(f"Delivery successful for {item.recipient}")
            # Save state after successful removal
            with self.lock:
                self._save_to_disk()
        else:
            item.attempts += 1
            if item.attempts < len(RETRY_INTERVALS):
                # Calculate next retry time
                backoff = RETRY_INTERVALS[item.attempts]
                item.delivery_time = time.time() + backoff
                
                log_error(f"Delivery failed for {item.recipient}. Retrying in {backoff}s (Attempt {item.attempts})")
                
                with self.lock:
                    heapq.heappush(self.queue, item)
                    self._save_to_disk()
            else:
                log_error(f"Max retries reached. Message for {item.recipient} discarded.")

    def _save_to_disk(self):
        """Persists current queue to JSON[cite: 112]."""
        try:
            data = [item.to_dict() for item in self.queue]
            with open(self.persistence_file, 'w') as f:
                json.dump(data, f)
        except IOError as e:
            log_error(f"Queue persistence failed: {e}")

    def _load_from_disk(self):
        """Loads queue from JSON on startup."""
        if not os.path.exists(self.persistence_file):
            return
        try:
            with open(self.persistence_file, 'r') as f:
                data = json.load(f)
                for entry in data:
                    item = QueueItem(**entry)
                    heapq.heappush(self.queue, item)
            log_info(f"Restored {len(self.queue)} items from disk")
        except (IOError, json.JSONDecodeError) as e:
            log_error(f"Failed to load queue persistence: {e}")