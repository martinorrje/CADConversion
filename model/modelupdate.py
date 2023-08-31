from PyQt5.QtCore import Qt
from PyQt5.QtCore import QMetaObject
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import time
import threading
import os


class Watcher:
    def __init__(self, filename, window):
        self.window = window
        self.DIRECTORY_TO_WATCH = None
        self.FILE_TO_WATCH = None
        self.observer = None
        self.thread = None
        self.watch_new_file(filename)


    def run(self):
        event_handler = Handler(self.window)
        self.observer.schedule(event_handler, self.DIRECTORY_TO_WATCH, recursive=False)
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True  # Daemon threads will be killed once the main program exits
        self.thread.start()

    def watch_new_file(self, filename):
        self.DIRECTORY_TO_WATCH = os.path.dirname(filename)
        self.FILE_TO_WATCH = os.path.basename(filename)
        self.observer = Observer()
        self.thread = None

    def _run(self):
        self.observer.start()
        self.observer.join()

    def stop(self):
        self.observer.stop()
        self.observer.join()
        if self.thread.is_alive():
            self.thread.join()


class Handler(FileSystemEventHandler):
    def __init__(self, window):
        self.window = window

    def process(self, event):
        filename = event.src_path
        if filename == self.window.file_to_watch and event.event_type == 'modified':
            # Use QMetaObject to invoke a method in the main thread safely
            QMetaObject.invokeMethod(self.window, 'show_update_model_popup', Qt.QueuedConnection)

    def on_modified(self, event):
        self.process(event)

    def on_created(self, event):
        self.process(event)
