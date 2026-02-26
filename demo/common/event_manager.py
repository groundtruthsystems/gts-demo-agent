import atexit
import datetime
import json
import logging
import os  # Used for checking file existence
import threading
import uuid
from typing import Optional

from pydantic import BaseModel, field_serializer

from demo.common.logger import setup_logger

# Configure basic logging for feedback
# You might want to customize this based on your application's logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(threadName)s] - %(levelname)s - %(message)s'
)

logger = setup_logger(__name__)

class AnalyticsEvent(BaseModel):
    id: Optional[str]
    correlation: str
    event_type: str
    timestamp: datetime.datetime = datetime.datetime.now(datetime.UTC)
    payload: dict = {}

    @field_serializer('timestamp')
    def serialize_timestamp(self, v: datetime.datetime):
        """Serializes timestamp to YYYY-MM-dd HH:mm:ss format."""
        return v.strftime("%Y-%m-%d %H:%M:%S")

    @classmethod
    def new(cls, correlation: str, event_type: str, payload: dict = {},):
        id = str(uuid.uuid4())
        return AnalyticsEvent(
            id=id,
            correlation=correlation,
            event_type=event_type,
            timestamp=datetime.datetime.now(datetime.UTC),
            payload=payload
        )


class EventManager:
    """
    A static-like class to manage and flush events to a JSON file.

    Events are accumulated in memory and flushed periodically and on program exit.
    Uses class methods and variables, so no instantiation is needed.
    Designed to be thread-safe.
    """
    # --- Class Variables ---
    _events = []  # In-memory list to store events before flushing
    _lock = threading.Lock()  # Lock to ensure thread-safe access to shared resources
    _filename = "events.json" # Default output filename
    _flush_interval_seconds = 30.0 # Default time between automatic flushes
    _timer = None # Holds the threading.Timer object for interval flushing
    _initialized = False # Flag to track if initialization (atexit, timer) has run
    _is_flushing = False # Flag to prevent concurrent/re-entrant flush calls

    # --- Configuration ---
    @classmethod
    def configure(cls, filename="events.json", interval=30.0):
        """
        Optional: Configure the filename and flush interval BEFORE the first push.

        Args:
            filename (str): Path to the JSON file where events will be flushed.
            interval (float): Interval in seconds for periodic flushing. Must be > 0.

        Raises:
            ValueError: If filename is invalid or interval is not positive.
            RuntimeError: If called after the EventManager has already been initialized.
        """
        with cls._lock:
            if cls._initialized:
                # Configuration should happen before the first event is pushed
                raise RuntimeError("EventManager already initialized. Cannot reconfigure.")
            if not isinstance(filename, str) or not filename:
                raise ValueError("Filename must be a non-empty string.")
            if not isinstance(interval, (int, float)) or interval <= 0:
                raise ValueError("Interval must be a positive number.")

            cls._filename = filename
            cls._flush_interval_seconds = float(interval)
            logging.info(f"EventManager configured: File='{cls._filename}', Interval={cls._flush_interval_seconds}s")

    # --- Core Functionality ---
    @classmethod
    def push(cls, event: AnalyticsEvent):
        """
        Adds an event to the in-memory queue. Events should be JSON-serializable dictionaries.

        Args:
            event (dict): The event data to store.
        """
        if not isinstance(event, AnalyticsEvent):
            logging.warning(f"Event must be an event, received {type(event)}. Skipping.")
            return


        with cls._lock:
            # Lazy initialization: Set up timer and exit handler on the first push
            if not cls._initialized:
                cls._initialize()

            event_id = uuid.uuid4()
            event.id = str(event_id)
            cls._events.append(event)
            # logging.debug(f"Event pushed: {event}") # Uncomment for verbose logging

    @classmethod
    def flush(cls):
        """
        Flushes pending events from memory to the configured JSON file.

        This method reads the existing file content (if it's a valid JSON list),
        appends the new events currently in memory, and writes the entire list back.
        It's designed to be safe to call manually, but is also called by the timer
        and the exit handler.
        """
        with cls._lock:
            # Prevent concurrent flushes (e.g., timer firing while exit handler is running)
            if cls._is_flushing:
                logging.warning("Flush called while already flushing. Skipping.")
                return

            if not cls._events:
                # logging.debug("No events to flush.") # Can be noisy
                return # Nothing to do

            # Set flag, copy events to flush, and clear the main list atomically
            cls._is_flushing = True
            events_to_write = list(cls._events) # Create a copy to work with
            cls._events.clear() # Clear the main list

        # --- Perform file I/O OUTSIDE the main lock to avoid blocking pushes ---
        logging.info(f"Attempting to flush {len(events_to_write)} events to '{cls._filename}'...")
        try:
            # 1. Read existing data from the file
            existing_data = []
            if os.path.exists(cls._filename):
                try:
                    with open(cls._filename, 'r', encoding='utf-8') as f:
                        file_content = f.read().strip()
                        if file_content: # Avoid JSONDecodeError on empty file
                            data = json.loads(file_content)
                            if isinstance(data, list):
                                existing_data = data
                            else:
                                logging.warning(f"Existing content in '{cls._filename}' is not a JSON list. File will be overwritten with new events.")
                        # If file exists but is empty, existing_data remains []
                except json.JSONDecodeError:
                    logging.warning(f"Could not decode JSON from '{cls._filename}'. File will be overwritten.")
                except IOError as e:
                    logging.error(f"Error reading '{cls._filename}': {e}. Attempting to overwrite.")
                except Exception as e: # Catch other potential issues during read/parse
                    logging.error(f"Unexpected error reading/parsing '{cls._filename}': {e}. Attempting to overwrite.")

            def convert_if_not_dict(event):
                if isinstance(event, AnalyticsEvent):
                    return event.model_dump()
                else:
                    return event
            # 2. Combine existing data with new events
            all_data = [convert_if_not_dict(n) for n in (existing_data + events_to_write)]

            # 3. Write the combined data back (overwrite mode)
            with open(cls._filename, 'w', encoding='utf-8') as f:

                json.dump(all_data, f, indent=4) # Use indent=4 for pretty-printing

            logging.info(f"Successfully flushed {len(events_to_write)} events.")

        except IOError as e:
            logging.error(f"Failed to write events to '{cls._filename}': {e}")
            # Strategy for failed write: Log the error.
            # Consider adding events back to the queue, but be wary of persistent errors:
            # with cls._lock:
            #     cls._events = events_to_write + cls._events # Prepend to retry later
        except Exception as e:
            logging.error(f"An unexpected error occurred during flush operation: {e}")
        finally:
            # --- Reset flushing flag inside lock ---
            with cls._lock:
                cls._is_flushing = False

    # --- Internal Helper Methods ---
    @classmethod
    def _initialize(cls):
        """Internal method for one-time setup. Assumes lock is held."""
        if cls._initialized:
            return # Already done

        # Register the exit handler to flush on program termination
        atexit.register(cls._exit_handler)

        # Start the periodic flush timer
        cls._start_timer()

        cls._initialized = True
        logging.info(f"EventManager initialized. Auto-flushing to '{cls._filename}' every {cls._flush_interval_seconds}s.")

    @classmethod
    def _start_timer(cls):
        """Starts/restarts the interval flush timer. Assumes lock is held or called safely."""
        if cls._timer:
            cls._timer.cancel() # Cancel any existing timer

        # Create and start a new timer thread
        cls._timer = threading.Timer(cls._flush_interval_seconds, cls._interval_flush_task)
        cls._timer.daemon = True # Allows program to exit even if timer thread is waiting
        cls._timer.start()
        logging.debug(f"Flush timer scheduled. Next check in {cls._flush_interval_seconds}s.")

    @classmethod
    def _stop_timer(cls):
        """Stops the interval timer. Assumes lock is held."""
        if cls._timer:
            cls._timer.cancel()
            cls._timer = None # Clear the timer reference
            logging.info("Interval flush timer stopped.")

    @classmethod
    def _interval_flush_task(cls):
        """Task executed by the timer thread."""
        logging.debug("Interval timer triggered flush task.")
        cls.flush() # Perform the flush

        # Reschedule the timer for the next interval *after* flushing
        with cls._lock:
            # Check if timer wasn't stopped by _exit_handler in the meantime
            if cls._initialized and cls._timer is not None:
                cls._start_timer() # Reschedule the timer

    @classmethod
    def _exit_handler(cls):
        """Function registered with atexit for cleanup."""
        logging.info("Program exiting. Performing final event flush...")
        # 1. Stop the interval timer to prevent it interfering
        with cls._lock:
            cls._stop_timer()
        # 2. Perform the final flush
        cls.flush()
        logging.info("EventManager exit handler finished.")
