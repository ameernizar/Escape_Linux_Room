"""Private API-to-worker provisioning; never send worker credentials to browsers."""
import http.client
import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .config import settings

class WorkerConnection(http.client.HTTPConnection):
    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(settings.terminal_worker_socket)

def prepare_shell(team_id: int, seed: str) -> None:
    path = f"/internal/teams/{team_id}/provision"
    body = json.dumps({"seed": seed}).encode()
    headers = {"Content-Type": "application/json", "X-Worker-Key": settings.secret_key}
    try:
        if settings.terminal_worker_socket:
            connection = WorkerConnection("localhost", timeout=90)
            try:
                connection.request("POST", path, body, headers)
                response = connection.getresponse()
                if response.status != 200:
                    raise ValueError("Worker refused provisioning")
                result = json.loads(response.read())
            finally:
                connection.close()
        else:
            request = Request(settings.terminal_worker_url.rstrip("/") + path, data=body, headers=headers, method="POST")
            with urlopen(request, timeout=90) as response:
                result = json.load(response)
        if result.get("status") != "ready" or result.get("team_id") != team_id:
            raise ValueError("Unexpected worker response")
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, http.client.HTTPException) as error:
        raise RuntimeError("Shell setup is unavailable. Use Prepare shell to retry; the team registration is saved.") from error
