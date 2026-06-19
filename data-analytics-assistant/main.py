"""
Main entrypoint for the AI-Powered Data Analytics Assistant.
Run: streamlit run main.py
"""
import subprocess
import sys

if __name__ == "__main__":
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", "app/ui/streamlit_app.py",
         "--server.port=8501", "--server.address=0.0.0.0"],
        check=True,
    )
