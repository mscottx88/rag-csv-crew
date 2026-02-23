"""Development server launcher for RAG CSV Crew.

Launches both backend (FastAPI) and frontend (Vite) servers in separate processes
and handles graceful shutdown on keyboard interrupt.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)

Usage:
    python launch.py
"""

from pathlib import Path
import signal
import subprocess
import sys
import time
from typing import NoReturn


def start_backend(script_dir: Path) -> subprocess.Popen[bytes]:
    """Start the backend FastAPI server.

    Args:
        script_dir: Root directory of the project

    Returns:
        Backend process handle

    Raises:
        subprocess.SubprocessError: If backend fails to start
    """
    print("Starting backend server (FastAPI on http://localhost:8000)...")
    backend_cwd: Path = script_dir / "backend"
    # pylint: disable=consider-using-with
    # JUSTIFICATION: Process must remain open beyond this function scope for monitoring
    backend_process: subprocess.Popen[bytes] = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.main:app", "--reload", "--port", "8000"],
        cwd=str(backend_cwd),
        # Inherit parent's stdout/stderr so output is displayed in console
    )
    print(f"[OK] Backend started (PID: {backend_process.pid})")
    return backend_process


def start_frontend(script_dir: Path) -> subprocess.Popen[bytes]:
    """Start the frontend Vite server.

    Args:
        script_dir: Root directory of the project

    Returns:
        Frontend process handle

    Raises:
        subprocess.SubprocessError: If frontend fails to start
    """
    print("Starting frontend server (Vite on http://localhost:5173)...")
    frontend_cwd: Path = script_dir / "frontend"
    # pylint: disable=consider-using-with
    # JUSTIFICATION: Process must remain open beyond this function scope for monitoring
    frontend_process: subprocess.Popen[bytes] = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(frontend_cwd),
        # Inherit parent's stdout/stderr so output is displayed in console
        shell=True,  # Required for npm on Windows
    )
    print(f"[OK] Frontend started (PID: {frontend_process.pid})")
    return frontend_process


def stop_process(process: subprocess.Popen[bytes], name: str, use_ctrl_c: bool = False) -> None:
    """Stop a process gracefully, with fallback to kill.

    Args:
        process: Process to stop
        name: Process name for logging
        use_ctrl_c: Whether to send CTRL_C_EVENT on Windows (for npm)
    """
    print(f"Stopping {name}...")
    try:
        if use_ctrl_c and sys.platform == "win32":
            process.send_signal(signal.CTRL_C_EVENT)
        else:
            process.terminate()
        process.wait(timeout=5)
        print(f"[OK] {name} stopped")
    except subprocess.TimeoutExpired:
        print(f"[WARN] {name} didn't stop gracefully, killing...")
        process.kill()
        print(f"[OK] {name} killed")
    except (OSError, ValueError) as e:
        print(f"[WARN] Error stopping {name}: {e}")
        process.kill()


def monitor_processes(
    backend_process: subprocess.Popen[bytes],
    frontend_process: subprocess.Popen[bytes],
) -> None:
    """Monitor running processes and exit if either dies.

    Args:
        backend_process: Backend process handle
        frontend_process: Frontend process handle

    Raises:
        SystemExit: If either process exits unexpectedly
    """
    while True:
        backend_status: int | None = backend_process.poll()
        frontend_status: int | None = frontend_process.poll()

        if backend_status is not None:
            print(f"\n[ERROR] Backend process exited with code {backend_status}")
            sys.exit(1)

        if frontend_status is not None:
            print(f"\n[ERROR] Frontend process exited with code {frontend_status}")
            sys.exit(1)

        time.sleep(1)


def main() -> NoReturn:
    """Launch backend and frontend servers with graceful shutdown handling.

    Starts:
    - Backend: uvicorn src.main:app --reload --port 8000 (in backend/ directory)
    - Frontend: npm run dev (in frontend/ directory)

    Both processes are monitored and terminated gracefully on Ctrl+C.
    """
    backend_process: subprocess.Popen[bytes] | None = None
    frontend_process: subprocess.Popen[bytes] | None = None

    try:
        print("=" * 60)
        print("RAG CSV Crew - Development Server Launcher")
        print("=" * 60)
        print()

        # Start both servers
        script_dir: Path = Path(__file__).parent
        backend_process = start_backend(script_dir)
        print()

        # Wait for backend to initialize
        time.sleep(2)

        frontend_process = start_frontend(script_dir)
        print()

        print("=" * 60)
        print("Servers running. Press Ctrl+C to stop.")
        print("=" * 60)
        print()
        print("Backend:  http://localhost:8000")
        print("Frontend: http://localhost:5173")
        print("API Docs: http://localhost:8000/docs")
        print()

        # Monitor processes - blocks until interrupted or process dies
        monitor_processes(backend_process, frontend_process)
        # Should never reach here, but satisfy type checker
        sys.exit(0)

    except KeyboardInterrupt:
        print("\n")
        print("=" * 60)
        print("Shutting down servers...")
        print("=" * 60)

        # Terminate processes gracefully
        if backend_process is not None:
            stop_process(backend_process, "backend server")

        if frontend_process is not None:
            stop_process(frontend_process, "frontend server", use_ctrl_c=True)

        print()
        print("All servers stopped. Goodbye!")
        sys.exit(0)

    except (subprocess.SubprocessError, OSError) as e:
        print(f"\n[ERROR] Process error: {e}")
        # Clean up processes
        if backend_process is not None:
            backend_process.kill()
        if frontend_process is not None:
            frontend_process.kill()
        sys.exit(1)


if __name__ == "__main__":
    main()
