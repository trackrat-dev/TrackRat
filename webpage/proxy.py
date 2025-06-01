import http.server
import socketserver
import urllib.request
import json

class SimpleProxyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/'):
            # Proxy API requests
            api_url = f"http://localhost:8000{self.path}"  # Remove /api prefix
            print(api_url)
            try:
                with urllib.request.urlopen(api_url) as response:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(response.read())
            except:
                self.send_error(502, "API server unavailable")
        else:
            # Serve static files
            super().do_GET()

PORT = 9998
with socketserver.TCPServer(("", PORT), SimpleProxyHandler) as httpd:
    print(f"Server with API proxy running on http://localhost:{PORT}")
    httpd.serve_forever()
