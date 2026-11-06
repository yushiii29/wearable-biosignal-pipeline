"""仅在本机启动 Jupyter；保留随机登录令牌，不向局域网开放。"""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parent
env = os.environ.copy()
for key, folder in {
    "JUPYTER_CONFIG_DIR": ".jupyter/config",
    "JUPYTER_DATA_DIR": ".jupyter/data",
    "JUPYTER_RUNTIME_DIR": ".runtime",
    "IPYTHONDIR": ".jupyter/ipython",
    "MPLCONFIGDIR": ".jupyter/matplotlib",
}.items():
    location = root / folder
    location.mkdir(parents=True, exist_ok=True)
    env[key] = str(location)
print("正在打开本地 Jupyter。关闭终端会停止服务。", flush=True)
args = [sys.executable, "-m", "jupyterlab", "--ip=127.0.0.1", "--port=8890",
        "--ServerApp.port_retries=10", f"--ServerApp.root_dir={root}",
        "--LabApp.default_url=/lab/tree/00_多传感器原型演示.ipynb"]
raise SystemExit(subprocess.call(args + sys.argv[1:], cwd=root, env=env))

