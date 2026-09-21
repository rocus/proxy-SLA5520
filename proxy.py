#!/usr/bin/env python3

import socket
import ssl
import threading
from datetime import datetime
from urllib.parse import urlparse, urljoin

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 8080

BUFFER_SIZE = 8192
MAX_REDIRECTS = 10

print_lock = threading.Lock()


def log(client, message):
    """Write one concise, timestamped log line."""
    client_name = f"{client[0]}:{client[1]}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with print_lock:
        print(
            f"{timestamp}  {client_name}  {message}",
            flush=True
        )


def describe_error(error):
    if isinstance(error, socket.timeout):
        return "timeout"

    if isinstance(error, socket.gaierror):
        return f"DNS error: {error}"

    if isinstance(error, ConnectionRefusedError):
        return "connection refused"

    if isinstance(error, ConnectionResetError):
        return "connection reset"

    if isinstance(error, BrokenPipeError):
        return "connection closed"

    if isinstance(error, ssl.SSLCertVerificationError):
        return "TLS certificate verify failed"

    if isinstance(error, ssl.SSLError):
        return f"TLS error: {error}"

    if isinstance(error, OSError):
        return str(error)

    return str(error)


def get_response_headers(server):
    """Read until the complete HTTP header block has arrived."""
    response = b""

    while b"\r\n\r\n" not in response:
        data = server.recv(BUFFER_SIZE)

        if not data:
            raise ConnectionError("station closed connection")

        response += data

    header_end = response.find(b"\r\n\r\n") + 4

    return response[:header_end], response[header_end:]


def parse_status(headers):
    first_line = headers.split(b"\r\n", 1)[0]
    parts = first_line.split()

    if len(parts) >= 2:
        try:
            return int(parts[1])
        except ValueError:
            pass

    return 0


def find_header(headers, name):
    name = name.lower().encode("ascii")

    for line in headers.split(b"\r\n"):
        if b":" not in line:
            continue

        key, value = line.split(b":", 1)

        if key.strip().lower() == name:
            return value.strip().decode("iso-8859-1")

    return None


def https_version(url):
    """Return the HTTPS equivalent of an HTTP URL."""
    parsed = urlparse(url)

    if parsed.scheme.lower() == "https":
        return url

    host = parsed.hostname

    if not host:
        raise ValueError("no hostname")

    netloc = host

    if parsed.port and parsed.port != 80:
        netloc += f":{parsed.port}"

    return parsed._replace(
        scheme="https",
        netloc=netloc
    ).geturl()


def connect_to_url(url, client):
    """
    Connect to a URL and follow redirects.

    Returns:
        server, response_headers, initial_data
    """

    redirects = 0

    while True:
        parsed = urlparse(url)

        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"unsupported scheme {parsed.scheme}"
            )

        host = parsed.hostname

        if not host:
            raise ValueError("no hostname")

        port = parsed.port or (
            443 if parsed.scheme == "https" else 80
        )

        path = parsed.path or "/"

        if parsed.query:
            path += "?" + parsed.query

        server = socket.create_connection(
            (host, port),
            timeout=15
        )

        try:
            # Establish TLS for HTTPS.
            if parsed.scheme == "https":
                context = ssl.create_default_context()

                server = context.wrap_socket(
                    server,
                    server_hostname=host
                )

            outgoing = (
                f"GET {path} HTTP/1.0\r\n"
                f"Host: {host}\r\n"
                "Icy-MetaData: 1\r\n"
                "User-Agent: NSPlayer/10.0.0.0\r\n"
                "Accept: */*\r\n"
                "\r\n"
            ).encode("ascii")

            server.sendall(outgoing)

            headers, initial_data = \
                get_response_headers(server)

            status = parse_status(headers)

            # Successful response.
            if 200 <= status < 300:

                # The connection is now a streaming connection,
                # so remove the connect timeout.
                server.settimeout(None)

                content_type = find_header(
                    headers,
                    "Content-Type"
                )

                bitrate = find_header(
                    headers,
                    "icy-br"
                )

                audio = content_type or "unknown format"

                if bitrate:
                    audio += f" {bitrate} kbps"

                log(client, f"OK {audio}")

                return server, headers, initial_data

            # Redirect.
            if 300 <= status < 400:

                location = find_header(
                    headers,
                    "Location"
                )

                if not location:
                    raise ConnectionError(
                        f"HTTP {status}, no Location"
                    )

                new_url = urljoin(url, location)

                log(
                    client,
                    f"{status} -> {new_url}"
                )

                server.close()

                redirects += 1

                if redirects > MAX_REDIRECTS:
                    raise ConnectionError(
                        "too many redirects"
                    )

                url = new_url
                continue

            # Other HTTP response.
            raise ConnectionError(
                f"HTTP {status}"
            )

        except Exception:
            try:
                server.close()
            except Exception:
                pass

            raise


def handle_client(client_socket, client):
    server = None

    try:
        # Read the SLA5520 request.
        request = b""

        while b"\r\n\r\n" not in request:
            data = client_socket.recv(BUFFER_SIZE)

            if not data:
                return

            request += data

        first_line = request.split(
            b"\r\n",
            1
        )[0]

        parts = first_line.split()

        if len(parts) < 2 or parts[0] != b"GET":
            log(client, "unsupported request")
            return

        url = parts[1].decode("ascii")

        log(client, f"GET {url}")

        parsed = urlparse(url)

        if not parsed.hostname:
            log(client, "FAILED invalid URL")
            return

        # The SLA5520 should normally give us an HTTP URL.
        # Try HTTP first.
        http_url = url

        # If necessary, try the HTTPS equivalent.
        https_url = https_version(url)

        # -------------------------------------------------
        # Try HTTP first
        # -------------------------------------------------

        try:
            server, headers, initial_data = \
                connect_to_url(
                    http_url,
                    client
                )

        except Exception as error:
            log(
                client,
                f"HTTP failed: {describe_error(error)}"
            )

            # -------------------------------------------------
            # Try HTTPS
            # -------------------------------------------------

            try:
                server, headers, initial_data = \
                    connect_to_url(
                        https_url,
                        client
                    )

            except Exception as error:
                log(
                    client,
                    f"HTTPS failed: {describe_error(error)}"
                )

                log(client, "FAILED")
                return

        # Send final station response to the SLA5520.
        client_socket.sendall(headers)

        if initial_data:
            client_socket.sendall(initial_data)

        # -------------------------------------------------
        # Relay the audio stream
        # -------------------------------------------------

        while True:
            data = server.recv(BUFFER_SIZE)

            if not data:
                log(client, "END station closed")
                break

            try:
                client_socket.sendall(data)

            except BrokenPipeError:
                log(client, "END error: BrokenPipeError")
                break

            except ConnectionResetError:
                log(client, "END error: ConnectionResetError")
                break

    except Exception as error:
        log(
            client,
            f"END error: {describe_error(error)}"
        )

    finally:
        if server is not None:
            try:
                server.close()
            except Exception:
                pass

        try:
            client_socket.close()
        except Exception:
            pass


def main():
    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    sock.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    sock.bind(
        (LISTEN_HOST, LISTEN_PORT)
    )

    sock.listen(10)

    print(
        f"HTTP/HTTPS relay listening on port "
        f"{LISTEN_PORT}",
        flush=True
    )

    print(
        "Press Ctrl-C to stop.",
        flush=True
    )

    try:
        while True:
            client_socket, address = sock.accept()

            # address is (IP, source_port)
            client = address

            thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client),
                daemon=True
            )

            thread.start()

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        sock.close()


if __name__ == "__main__":
    main()
