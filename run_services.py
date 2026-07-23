"""
Run all microservices locally for development (without Docker).
Requires: pip install uvicorn fastapi httpx sqlalchemy aiosqlite

Usage: python run_services.py
"""

import subprocess
import sys
import os
import time
import signal

SERVICES = [
    {"name": "auth", "port": 8001, "dir": "services/auth"},
    {"name": "documents", "port": 8002, "dir": "services/documents"},
    {"name": "chat", "port": 8003, "dir": "services/chat"},
    {"name": "gateway", "port": 8080, "dir": "services/gateway"},
]

processes = []


def start_all():
    root = os.path.dirname(os.path.abspath(__file__))
    for svc in SERVICES:
        svc_dir = os.path.join(root, svc["dir"])
        print(f"Starting {svc['name']} on port {svc['port']}...")
        proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", str(svc["port"]), "--reload"],
            cwd=svc_dir,
            env={**os.environ, "DATABASE_URL": f"sqlite+aiosqlite:///./{svc['name']}.db"},
        )
        processes.append(proc)
        time.sleep(1)

    print(f"\n{'='*50}")
    print("All services running:")
    print(f"  Gateway:   http://localhost:8080")
    print(f"  Auth:      http://localhost:8001")
    print(f"  Documents: http://localhost:8002")
    print(f"  Chat:      http://localhost:8003")
    print(f"  Frontend:  cd frontend && npm run dev")
    print(f"{'='*50}")
    print("Press Ctrl+C to stop all services.\n")


def stop_all(sig=None, frame=None):
    print("\nStopping all services...")
    for proc in processes:
        proc.terminate()
    for proc in processes:
        proc.wait()
    print("All services stopped.")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stop_all)
    signal.signal(signal.SIGTERM, stop_all)
    start_all()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        stop_all()
