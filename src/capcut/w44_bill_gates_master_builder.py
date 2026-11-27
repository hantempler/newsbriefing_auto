"""
PRJ_StarIsBorn: src/capcut/w44_bill_gates_master_builder.py
evergreen/src/capcut/w44_bill_gates_master_builder.py 와 100% 동일 실행 링크
"""

import sys
from pathlib import Path

evergreen_script = Path(__file__).resolve().parent.parent.parent / "evergreen" / "src" / "capcut" / "w44_bill_gates_master_builder.py"

if __name__ == "__main__":
    if evergreen_script.exists():
        import subprocess
        cmd = [sys.executable, str(evergreen_script)]
        subprocess.run(cmd, check=True)
    else:
        print(f"Error: {evergreen_script} not found")

