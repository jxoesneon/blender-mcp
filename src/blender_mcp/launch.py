#!/usr/bin/env python3
"""
Blender MCP Launcher — starts Blender with --enable-event-simulate,
auto-starts the MCP socket server, then execs the MCP stdio server.

Usage:
    blender-mcp-launch [--blender PATH] [--host HOST] [--port PORT] [extra blender args...]

Environment variables:
    BLENDER_PATH   - path to Blender binary (default: auto-detect)
    BLENDER_HOST   - socket host (default: 127.0.0.1)
    BLENDER_PORT   - socket port (default: 9876)
    BLENDER_MCP_NO_LAUNCH - if set, skip launching Blender (assume it's already running)
"""

from __future__ import annotations

import os
import sys
import time
import socket
import subprocess
import shutil
import signal

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9876


def find_blender() -> str:
    """Auto-detect the Blender binary path."""
    path = os.environ.get("BLENDER_PATH")
    if path and os.path.isfile(path):
        return path
    for candidate in [
        "/Applications/Blender.app/Contents/MacOS/Blender",
        "/opt/homebrew/bin/blender",
        "/usr/local/bin/blender",
        "/usr/bin/blender",
    ]:
        if os.path.isfile(candidate):
            return candidate
    found = shutil.which("blender")
    if found:
        return found
    raise FileNotFoundError(
        "Could not find Blender binary. Set BLENDER_PATH env var or pass --blender PATH."
    )


def wait_for_socket(host: str, port: int, timeout: float = 60.0) -> bool:
    """Wait until the MCP socket server is accepting connections."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return True
        except (ConnectionRefusedError, socket.timeout, OSError):
            time.sleep(0.5)
    return False


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Launch Blender with --enable-event-simulate and start the MCP server.",
        add_help=False,
    )
    parser.add_argument("--blender", default=None, help="Path to Blender binary")
    parser.add_argument("--host", default=None, help="MCP socket host")
    parser.add_argument("--port", type=int, default=None, help="MCP socket port")
    parser.add_argument("--no-launch", action="store_true",
                        help="Don't launch Blender (assume it's already running)")
    parser.add_argument("--blend-file", default=None, help="Optional .blend file to open")
    args, remaining = parser.parse_known_args()

    host = args.host or os.environ.get("BLENDER_HOST", DEFAULT_HOST)
    port = args.port or int(os.environ.get("BLENDER_PORT", DEFAULT_PORT))
    no_launch = args.no_launch or os.environ.get("BLENDER_MCP_NO_LAUNCH")

    blender_proc = None

    # Check if Blender is already running with the socket server
    already_running = False
    try:
        with socket.create_connection((host, port), timeout=1.0):
            already_running = True
    except (ConnectionRefusedError, socket.timeout, OSError):
        pass

    if already_running:
        print(f"[blender-mcp-launch] Blender MCP server already running on {host}:{port}, connecting.", file=sys.stderr)
    elif not no_launch:
        blender_bin = args.blender or find_blender()

        blender_args = [
            blender_bin,
            "--enable-event-simulate",
        ]
        if args.blend_file:
            blender_args.append(args.blend_file)
        blender_args.extend(remaining)

        env = os.environ.copy()
        env["BLENDER_MCP_AUTOSTART"] = "1"
        env["BLENDER_HOST"] = host
        env["BLENDER_PORT"] = str(port)

        print(f"[blender-mcp-launch] Starting Blender: {' '.join(blender_args)}", file=sys.stderr)
        blender_proc = subprocess.Popen(
            blender_args,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        def _kill_blender(*_):
            if blender_proc and blender_proc.poll() is None:
                blender_proc.terminate()
                try:
                    blender_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    blender_proc.kill()
            sys.exit(0)

        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, _kill_blender)

    if not already_running:
        print(f"[blender-mcp-launch] Waiting for MCP socket on {host}:{port}...", file=sys.stderr)
        if not wait_for_socket(host, port, timeout=60.0):
            print("[blender-mcp-launch] ERROR: Blender MCP server did not start within 60s.", file=sys.stderr)
            if blender_proc:
                blender_proc.terminate()
            sys.exit(1)

    print("[blender-mcp-launch] Socket server is up. Starting MCP stdio server...", file=sys.stderr)

    mcp_server = os.path.join(os.path.dirname(__file__), "..", "..", ".venv", "bin", "blender-mcp")
    mcp_server = os.path.abspath(mcp_server)
    if not os.path.isfile(mcp_server):
        mcp_server = shutil.which("blender-mcp")
    if not mcp_server:
        print("[blender-mcp-launch] ERROR: Could not find blender-mcp server binary.", file=sys.stderr)
        if blender_proc:
            blender_proc.terminate()
        sys.exit(1)

    os.execv(mcp_server, [mcp_server])


if __name__ == "__main__":
    main()
