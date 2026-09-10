import os
import sys
import subprocess
from pathlib import Path


def main():
    root_dir = Path(__file__).resolve().parent
    venv_python = root_dir / ".venv" / "Scripts" / "python.exe"

    try:
        import uvicorn
    except ImportError:
        if venv_python.exists():
            print(f"[*] Switching to project virtual environment ({venv_python})...")
            result = subprocess.run([str(venv_python), str(__file__)] + sys.argv[1:])
            sys.exit(result.returncode)
        else:
            print("[-] Error: 'uvicorn' is not installed in the current Python environment.")
            print("[*] Activate your virtual environment: .\\.venv\\Scripts\\activate")
            print("[*] Or install dependencies: pip install -r requirements.txt")
            sys.exit(1)

    import uvicorn
    print("[*] Starting Personal Notes application on http://127.0.0.1:8000")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
