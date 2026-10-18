"""Windows-safe entry point. The adjacent CMD contains ASCII and CRLF only."""
from __future__ import annotations

from datetime import datetime
import argparse
import importlib.util
import os
from pathlib import Path
import runpy
import shutil
import sys
import traceback


class Tee:
    def __init__(self, terminal, logfile):
        self.terminal = terminal
        self.logfile = logfile

    def write(self, text):
        if self.terminal is not None:
            try:
                self.terminal.write(text)
            except UnicodeEncodeError:
                encoding = getattr(self.terminal, "encoding", None) or "utf-8"
                self.terminal.write(text.encode(encoding, "replace").decode(encoding))
        self.logfile.write(text)
        self.logfile.flush()
        return len(text)

    def flush(self):
        if self.terminal is not None:
            self.terminal.flush()
        self.logfile.flush()

    def isatty(self):
        return False


def main():
    parser = argparse.ArgumentParser(description="迈克耳孙干涉实验台")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-open", action="store_true", help="不自动打开浏览器")
    args = parser.parse_args()
    base = Path(__file__).resolve().parent
    work = base / "work"
    work.mkdir(exist_ok=True)
    log_path = work / "启动日志.txt"
    original_out, original_err = sys.stdout, sys.stderr
    with log_path.open("a", encoding="utf-8") as logfile:
        sys.stdout = Tee(original_out, logfile)
        sys.stderr = Tee(original_err, logfile)
        try:
            print(f"\n{'='*50}\n启动时间：{datetime.now():%Y-%m-%d %H:%M:%S}")
            print(f"Python：{sys.executable}")
            print(f"实验目录：{base}")
            print(f"启动日志：{log_path}")
            if sys.version_info < (3, 10):
                raise RuntimeError("需要 Python 3.10 或更高版本。")
            missing = [name for name in ("numpy", "scipy") if importlib.util.find_spec(name) is None]
            if missing:
                raise RuntimeError("缺少依赖：" + ", ".join(missing) +
                                   f'。请运行："{sys.executable}" -m pip install -r "{base / "应用" / "requirements.txt"}"')
            for tool in ("ffmpeg", "ffprobe"):
                if not shutil.which(tool):
                    raise RuntimeError(f"找不到 {tool}，请确认 FFmpeg 已加入 PATH。")
            app = base / "应用"
            server = app / "server.py"
            if not server.is_file():
                raise RuntimeError(f"程序文件缺失：{server}")
            os.chdir(app)
            sys.path.insert(0, str(app))
            sys.argv = [str(server), "--port", str(args.port)]
            if not args.no_open:
                sys.argv.append("--open")
            print("正在启动实验台，浏览器将自动打开。请保留此窗口。", flush=True)
            runpy.run_path(str(server), run_name="__main__")
            return 0
        except KeyboardInterrupt:
            print("\n实验台已停止。")
            return 0
        except Exception:
            traceback.print_exc()
            print(f"\n启动失败，完整信息已写入：{log_path}")
            return 1
        finally:
            sys.stdout, sys.stderr = original_out, original_err


if __name__ == "__main__":
    raise SystemExit(main())
