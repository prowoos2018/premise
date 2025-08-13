import sys, io, subprocess, os
from flask import Blueprint, render_template
from dotenv import load_dotenv

load_dotenv()
automation_bp = Blueprint('automation', __name__, url_prefix='/automation')

@automation_bp.route('/start_review')
def start_review():
    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf

    print("[Automation] start_review endpoint hit")

    env = os.environ.copy()
    env["CHROME_HEADLESS"] = "true"

    # xvfb-run 래핑
    cmd = [
        "xvfb-run", "--auto-servernum",
        "-s", "-screen 0 1920x1080x24",
        sys.executable, "-m", "scripts.run_all"
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )
    for line in proc.stdout:
        print(line.rstrip())
    proc.wait()

    sys.stdout = old_stdout
    logs = buf.getvalue().splitlines()
    return render_template('automation_result.html', logs=logs)
