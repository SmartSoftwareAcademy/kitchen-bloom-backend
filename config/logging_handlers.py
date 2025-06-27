import logging
import sys

class UnicodeSafeStreamHandler(logging.StreamHandler):
    """A StreamHandler that safely handles Unicode characters on Windows."""
    
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            
            # For Windows console, handle Unicode properly
            if hasattr(stream, 'buffer'):
                # Use the underlying buffer for binary writing
                stream.buffer.write(msg.encode('utf-8'))
                stream.buffer.flush()
            else:
                # Fallback to regular write
                stream.write(msg)
                stream.flush()
        except UnicodeEncodeError:
            # If Unicode encoding fails, try to encode with error handling
            try:
                msg = self.format(record)
                stream = self.stream
                if hasattr(stream, 'buffer'):
                    stream.buffer.write(msg.encode('utf-8', errors='replace'))
                    stream.buffer.flush()
                else:
                    stream.write(msg.encode('utf-8', errors='replace').decode('utf-8'))
                    stream.flush()
            except Exception:
                self.handleError(record)
        except Exception:
            self.handleError(record) 