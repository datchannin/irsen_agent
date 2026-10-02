"""Synchronous, standard-library TCP client for IRSEN Agent Bridge."""

import json
import socket
import time


class IrsenError(Exception):
    """Base class for client errors."""


class IrsenConnectionError(IrsenError):
    """Connection failed, was closed, or broke during a request."""


class IrsenTimeoutError(IrsenError):
    """The connection or request deadline expired."""


class IrsenProtocolError(IrsenError):
    """Invalid response or an explicit error returned by the bridge."""


class IrsenClient:
    """One request at a time; methods return the response's result field.

    Instances are not thread-safe. No retries or automatic reconnection.
    """

    def __init__(self, host="127.0.0.1", port=47621,
                 timeout=5.0, action_timeout=120.0):
        if not (0 < timeout < float("inf") and
                0 < action_timeout < float("inf")):
            raise ValueError("Timeouts must be finite positive numbers.")
        self.host = host
        self.port = port
        self.timeout = timeout
        self.action_timeout = action_timeout
        self._socket = None
        self._receive_buffer = bytearray()
        self._next_id = 1

    def connect(self):
        """Connect explicitly; calling again while connected is harmless."""
        if self._socket is not None:
            return
        try:
            self._socket = socket.create_connection(
                (self.host, self.port), timeout=self.timeout)
        except socket.timeout as exc:
            raise IrsenTimeoutError(
                f"Connection to {self.host}:{self.port} timed out "
                f"after {self.timeout:g}s.") from exc
        except OSError as exc:
            raise IrsenConnectionError(
                f"Cannot connect to {self.host}:{self.port}: {exc}") from exc
        self._receive_buffer.clear()

    def close(self):
        """Close the connection and discard any buffered response bytes."""
        connection = self._socket
        self._socket = None
        self._receive_buffer.clear()
        if connection is not None:
            connection.close()

    def ping(self):
        return self._request("ping")

    def get_combat_state(self):
        return self._request("get_combat_state")

    def get_available_actions(self):
        return self._request("get_available_actions")

    def perform_action(self, action_id):
        if not isinstance(action_id, str) or not action_id:
            raise ValueError("action_id must be a non-empty string.")
        return self._request("perform_action", action_id=action_id)

    def _request(self, command, **params):
        if self._socket is None:
            raise IrsenConnectionError("Not connected; call connect() first.")
        request_id = self._next_id
        self._next_id += 1
        request = {"id": request_id, "command": command, **params}
        data = (json.dumps(request, ensure_ascii=False, allow_nan=False)
                + "\n").encode("utf-8")
        timeout = (self.action_timeout if command == "perform_action"
                   else self.timeout)
        deadline = time.monotonic() + timeout
        try:
            self._socket.settimeout(timeout)
            self._socket.sendall(data)
            response = self._read_response(deadline)
            if not isinstance(response, dict):
                raise IrsenProtocolError("Response must be a JSON object.")
            response_id = response.get("id")
            # Python considers 1 == 1.0; reject bool, which also equals 1.
            if (type(response_id) not in (int, float) or
                    response_id != request_id):
                raise IrsenProtocolError(
                    f"Response ID {response_id!r} does not match "
                    f"request ID {request_id}.")
            if type(response.get("ok")) is not bool:
                raise IrsenProtocolError("Response must contain boolean 'ok'.")
            if response["ok"]:
                if "result" not in response:
                    raise IrsenProtocolError("Successful response lacks 'result'.")
            elif not isinstance(response.get("error"), str):
                raise IrsenProtocolError("Error response lacks string 'error'.")
        except socket.timeout as exc:
            self.close()
            detail = (" The action may already have executed; do not retry "
                      "it blindly." if command == "perform_action" else "")
            raise IrsenTimeoutError(
                f"{command} (id={request_id}) timed out after {timeout:g}s."
                f" Connection closed.{detail}") from exc
        except OSError as exc:
            self.close()
            raise IrsenConnectionError(
                f"{command} (id={request_id}): connection error: {exc}") from exc
        except (IrsenProtocolError, IrsenConnectionError):
            self.close()
            raise

        # A valid bridge error consumed one complete response; connection is usable.
        if not response["ok"]:
            raise IrsenProtocolError(
                f"Bridge rejected {command} (id={request_id}): "
                f"{response['error']}")
        return response["result"]

    def _read_response(self, deadline):
        while True:
            newline = self._receive_buffer.find(b"\n")
            if newline >= 0:
                line = bytes(self._receive_buffer[:newline])
                del self._receive_buffer[:newline + 1]
                try:
                    return json.loads(line.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise IrsenProtocolError(
                        f"Invalid UTF-8/JSON response: {exc}") from exc
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise socket.timeout("Request deadline expired.")
            self._socket.settimeout(remaining)
            chunk = self._socket.recv(4096)
            if not chunk:
                detail = (" in the middle of a response"
                          if self._receive_buffer else " before a response")
                raise IrsenConnectionError(f"Bridge closed the connection{detail}.")
            # Keep bytes until the whole line arrives, including split UTF-8.
            self._receive_buffer.extend(chunk)
