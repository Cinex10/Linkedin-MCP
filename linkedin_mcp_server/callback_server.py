"""Simple HTTP server to handle LinkedIn OAuth callbacks."""

import http.server
import socketserver
import urllib.parse
from typing import Optional
import threading
import time

from linkedin_mcp_server.config import get_config


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for OAuth callbacks."""
    
    # Class variable to store the callback URL
    callback_url: Optional[str] = None
    config = get_config()
    
    def do_GET(self):
        """Handle GET requests (OAuth callbacks)."""
        # Parse the URL and query parameters
        parsed_url = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Store the full callback URL
        CallbackHandler.callback_url = f"{self.config.redirect_uri}{self.path}"
        
        # Check if we got an authorization code
        if 'code' in query_params:
            # Success response
            response_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>LinkedIn Authentication</title>
                <meta charset="UTF-8">
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        text-align: center;
                        margin: 0;
                        padding: 50px 20px;
                        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                        min-height: 100vh;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;
                    }
                    .container {
                        background: white;
                        padding: 40px;
                        border-radius: 12px;
                        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                        max-width: 500px;
                        width: 100%;
                    }
                    .success {
                        color: #22c55e;
                        font-size: 32px;
                        font-weight: bold;
                        margin-bottom: 20px;
                    }
                    .close-instruction {
                        color: #6b7280;
                        font-size: 18px;
                        margin-top: 20px;
                    }
                    .checkmark {
                        color: #22c55e;
                        font-size: 64px;
                        margin-bottom: 20px;
                        font-weight: bold;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="checkmark">&#x2713;</div>
                    <div class="success">LinkedIn Authentication Successful!</div>
                    <div class="close-instruction">You can close this page now.</div>
                </div>
            </body>
            </html>
            """
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(response_html.encode('utf-8'))
            
        elif 'error' in query_params:
            # Error response
            error = query_params.get('error', ['Unknown error'])[0]
            error_description = query_params.get('error_description', [''])[0]
            
            response_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>LinkedIn Authentication</title>
                <meta charset="UTF-8">
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        text-align: center;
                        margin: 0;
                        padding: 50px 20px;
                        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
                        min-height: 100vh;
                        display: flex;
                        flex-direction: column;
                        justify-content: center;
                        align-items: center;
                    }
                    .container {
                        background: white;
                        padding: 40px;
                        border-radius: 12px;
                        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
                        max-width: 500px;
                        width: 100%;
                    }
                    .error {
                        color: #ef4444;
                        font-size: 32px;
                        font-weight: bold;
                        margin-bottom: 20px;
                    }
                    .error-details {
                        color: #6b7280;
                        font-size: 16px;
                        margin: 10px 0;
                    }
                    .close-instruction {
                        color: #6b7280;
                        font-size: 18px;
                        margin-top: 20px;
                    }
                    .error-icon {
                        color: #ef4444;
                        font-size: 64px;
                        margin-bottom: 20px;
                        font-weight: bold;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="error-icon">&#x2717;</div>
                    <div class="error">LinkedIn Authentication Failed</div>
                    <div class="error-details"><strong>Error:</strong> {error}</div>
                    <div class="error-details"><strong>Description:</strong> {error_description}</div>
                    <div class="close-instruction">You can close this page and try again.</div>
                </div>
            </body>
            </html>
            """
            
            self.send_response(400)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(response_html.encode('utf-8'))
        
        else:
            # Unexpected request
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Override to reduce log noise."""
        pass


class CallbackServerManager:
    """Singleton manager for the callback server lifecycle."""
    
    _instance: Optional['CallbackServerManager'] = None
    _server: Optional[socketserver.TCPServer] = None
    _thread: Optional[threading.Thread] = None
    _port: int = 8080
    
    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    def start_server(cls, port: int = 8080) -> None:
        """Start the callback server as part of MCP lifecycle."""
        if cls._server is not None:
            return  # Already running
        
        try:
            cls._port = port
            cls._server = socketserver.TCPServer(("", port), CallbackHandler)
            cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
            cls._thread.start()
            print(f"✅ Callback server started on http://localhost:{port}")
        except OSError as e:
            if e.errno == 48:  # Address already in use
                print(f"⚠️  Port {port} is already in use. Callback server not started automatically.")
                raise
            else:
                print(f"❌ Failed to start callback server: {e}")
                raise
    
    @classmethod
    def stop_server(cls) -> None:
        """Stop the callback server as part of MCP lifecycle."""
        if cls._server:
            cls._server.shutdown()
            cls._server.server_close()
            cls._server = None
            cls._thread = None
            print(f"✅ Callback server stopped")
    
    @classmethod
    def is_running(cls) -> bool:
        """Check if the callback server is running."""
        return cls._server is not None and cls._thread is not None and cls._thread.is_alive()
    
    @classmethod
    def get_port(cls) -> int:
        """Get the port the server is running on."""
        return cls._port
    
    @classmethod
    def get_callback_url(cls) -> Optional[str]:
        """Get the received callback URL."""
        return CallbackHandler.callback_url
    
    @classmethod
    def clear_callback_url(cls) -> None:
        """Clear the stored callback URL."""
        CallbackHandler.callback_url = None
    
    @classmethod
    def wait_for_callback(cls, timeout: int = 300) -> Optional[str]:
        """
        Wait for a callback URL to be received.
        
        Args:
            timeout: Maximum time to wait in seconds (default: 5 minutes)
            
        Returns:
            The callback URL if received, None if timeout
        """
        # Clear any previous callback URL
        cls.clear_callback_url()
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if CallbackHandler.callback_url:
                return CallbackHandler.callback_url
            time.sleep(1)
        return None


# Keep the CallbackServer class for backward compatibility
class CallbackServer:
    """Simple server to handle OAuth callbacks - Legacy wrapper around singleton manager."""
    
    def __init__(self, port: int = 8080):
        """Initialize the callback server."""
        self.port = port
        self.server: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None
    
    def start(self) -> None:
        """Start the callback server."""
        CallbackServerManager.start_server(self.port)
        # Update our references to match the singleton
        self.server = CallbackServerManager._server
        self.thread = CallbackServerManager._thread
    
    def stop(self) -> None:
        """Stop the callback server."""
        CallbackServerManager.stop_server()
        self.server = None
        self.thread = None
    
    def is_running(self) -> bool:
        """Check if the callback server is currently running."""
        return CallbackServerManager.is_running()
    
    def get_callback_url(self) -> Optional[str]:
        """Get the received callback URL."""
        return CallbackServerManager.get_callback_url()
    
    def clear_callback_url(self) -> None:
        """Clear the stored callback URL."""
        CallbackServerManager.clear_callback_url()
    
    def wait_for_callback(self, timeout: int = 300) -> Optional[str]:
        """Wait for a callback URL to be received."""
        return CallbackServerManager.wait_for_callback(timeout)


def run_callback_server(port: int = 8080):
    """Run the callback server interactively."""
    try:
        CallbackServerManager.start_server(port)
        print("\n" + "="*60)
        print("LinkedIn OAuth Callback Server")
        print("="*60)
        print(f"Server running on: http://localhost:{port}")
        print(f"Callback URL: http://localhost:{port}/callback")
        print("\nInstructions:")
        print("RECOMMENDED: Use authenticate_linkedin_oauth() for automatic one-step authentication")
        print("")
        print("This callback server is mainly used internally by authenticate_linkedin_oauth().")
        print("You typically don't need to run it manually unless doing custom integration.")
        print("\nPress Ctrl+C to stop the server")
        print("="*60)
        
        # Keep the server running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nShutting down server...")
            CallbackServerManager.stop_server()
            
    except Exception as e:
        print(f"Error running server: {e}")


if __name__ == "__main__":
    run_callback_server() 