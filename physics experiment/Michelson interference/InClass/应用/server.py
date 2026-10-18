"""Local-only, dependency-light HTTP app. Run: python server.py [--port 8765]."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import mimetypes
import os
from pathlib import Path
import re
import socket
import threading
from urllib.parse import urlparse, parse_qs, unquote
from urllib.request import urlopen
import uuid
import webbrowser

from analyzer import probe, analyze_video, audio_onsets, make_proxy

APP = Path(__file__).resolve().parent
ROOT = APP.parent
DATA = ROOT / "数据"
STATIC = APP / "static"
MEDIA = DATA / "视频副本"
RESULTS = DATA / "分析结果"
EXPORTS = ROOT / "报告与导出"
for folder in (MEDIA, RESULTS, EXPORTS):
    folder.mkdir(parents=True, exist_ok=True)
VIDEOS = {}
JOBS = {}
LOCK = threading.RLock()
POOL = ThreadPoolExecutor(max_workers=2)
SAMPLE = ROOT / "素材" / "波长测量.mp4"
CALIBRATION = {
    "um_per_turn": 10.0, "divisions_per_turn": 100, "um_per_division": .1,
    "name": "常见教学型微调鼓轮（100 格）", "status": "assumed_model",
    "note": "采用公开教学器材的标称档位；原视频未显示微调机构型号，尚未核验与实物一致。不是所有积木式位移台的统一标准。",
    "source_title": "西南大学：迈克耳孙干涉仪·粗调和微调鼓轮",
    "source_url": "https://wlxf.swu.edu.cn/__local/6/D0/50/0B459BF7155EBF7E251B1901401_3CF790E8_1933CA.pdf",
}


def add_video(path):
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    meta = probe(path)
    identity = uuid.uuid5(uuid.NAMESPACE_URL, meta["path"] + str(meta["size"]) + str(Path(path).stat().st_mtime_ns)).hex[:20]
    with LOCK:
        existing = VIDEOS.get(identity, {})
        meta.update({"id": identity, "url": f"/media/{identity}", "proxy": existing.get("proxy")})
        proxy = MEDIA / f"{identity}_preview.mp4"
        if proxy.is_file():
            meta["proxy"] = str(proxy)
        bundled_preview = path.parent / "预览" / path.name
        if not meta["proxy"] and bundled_preview.is_file():
            meta["proxy"] = str(bundled_preview.resolve())
        if meta["proxy"]:
            meta["preview_url"] = f"/media/{identity}?proxy=1"
        try:
            meta["portable_path"] = Path(meta["path"]).relative_to(ROOT).as_posix()
        except ValueError:
            pass
        VIDEOS[identity] = meta
    return meta


def start_job(kind, meta, options):
    identity = uuid.uuid4().hex[:16]
    cancel = threading.Event()
    job = {"id": identity, "state": "queued", "progress": 0, "message": "等待处理", "kind": kind, "video_id": meta["id"]}
    with LOCK:
        JOBS[identity] = (job, cancel)
    def progress(value, message):
        with LOCK:
            job.update(progress=round(float(value), 4), message=message)
    def worker():
        try:
            job.update(state="running")
            if cancel.is_set():
                raise ValueError("分析已取消。")
            if kind == "proxy":
                path = make_proxy(meta, MEDIA / f"{meta['id']}_preview.mp4", progress, cancel.is_set)
                with LOCK:
                    VIDEOS[meta["id"]]["proxy"] = path
                    VIDEOS[meta["id"]]["preview_url"] = f"/media/{meta['id']}?proxy=1"
                result = {"preview_url": f"/media/{meta['id']}?proxy=1"}
            elif kind == "audio":
                result = {"audio": audio_onsets(meta, options, progress, cancel.is_set)}
            else:
                video = analyze_video(meta, options, lambda v,m:progress(v*.78,m), cancel.is_set)
                audio = audio_onsets(meta, options, lambda v,m:progress(.78+v*.21,m), cancel.is_set)
                result = {"video": video, "audio": audio, "meta": meta, "calibration": CALIBRATION}
            if cancel.is_set():
                raise ValueError("分析已取消。")
            result["video_id"] = meta["id"]
            if kind != "proxy":
                output = RESULTS / f"{kind}_{datetime.now():%Y%m%d_%H%M%S}_{identity}.json"
                output.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
                result["saved_path"] = str(output)
            with LOCK:
                job.update(state="done", progress=1, message="处理完成", result=result)
        except Exception as exc:
            with LOCK:
                job.update(state="cancelled" if cancel.is_set() else "error", message=str(exc))
    POOL.submit(worker)
    return job.copy()


class LocalHTTPServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can bind over another active listener.
    allow_reuse_address = os.name != "nt"

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Handler(BaseHTTPRequestHandler):
    server_version = "MichelsonLab/1.3"

    def log_message(self, fmt, *args):
        # No user paths or JSON bodies are logged.
        if args and str(args[0]).startswith("GET /api/jobs"):
            return
        super().log_message(fmt, *args)

    def send_json(self, data, code=200):
        payload = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def json_body(self):
        size = int(self.headers.get("Content-Length", 0))
        if not 0 < size <= 150*1024*1024:
            raise ValueError("请求数据过大或为空。")
        return json.loads(self.rfile.read(size))

    def local_request(self):
        host = self.headers.get("Host", "").split(":")[0]
        origin = self.headers.get("Origin")
        return host in ("localhost", "127.0.0.1") and (not origin or origin == f"http://{self.headers.get('Host')}")

    def do_GET(self):
        if not self.local_request():
            self.send_json({"error": "只支持从本机打开。"}, 403)
            return
        parsed = urlparse(self.path)
        route = parsed.path
        try:
            if route == "/api/config":
                self.send_json({"root":str(ROOT), "sample":str(SAMPLE) if SAMPLE.is_file() else None, "calibration":CALIBRATION,
                                "features":{"spatial_phase":True,"wave_intervals":True,"spatial_parameters":True}, "version":"1.3",
                                "homework_report":"/homework/index.html" if (ROOT/"index.html").is_file() else None,
                                "homework_project":"/exports/实验项目.json" if (EXPORTS/"实验项目.json").is_file() else None})
            elif route.startswith("/api/jobs/"):
                identity=route.rsplit("/",1)[-1]
                with LOCK:
                    entry=JOBS.get(identity)
                    data=entry[0].copy() if entry else None
                self.send_json(data or {"error":"任务不存在"}, 200 if data else 404)
            elif route.startswith("/media/"):
                identity=route.rsplit("/",1)[-1]
                with LOCK:
                    meta=VIDEOS.get(identity)
                if not meta:
                    self.send_json({"error":"请重新导入视频。"},404)
                    return
                use_proxy = parse_qs(parsed.query).get("proxy",["0"])[0] == "1"
                self.send_file(Path(meta.get("proxy") or meta["path"]) if use_proxy else Path(meta["path"]))
            elif route.startswith("/exports/"):
                name=unquote(route[len("/exports/"):])
                if Path(name).name != name:
                    raise ValueError("文件名无效。")
                self.send_file(EXPORTS/name)
            elif route.startswith("/homework/"):
                target = (ROOT / unquote(route[len("/homework/"):])).resolve()
                if not target.is_relative_to(ROOT):
                    raise ValueError("文件路径无效。")
                self.send_file(target)
            else:
                relative = "index.html" if route == "/" else unquote(route).lstrip("/")
                target=(STATIC/relative).resolve()
                if not target.is_relative_to(STATIC):
                    self.send_json({"error":"路径无效"},403)
                    return
                self.send_file(target)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as exc:
            self.send_json({"error":str(exc)},400)

    def send_file(self,path):
        if not path.is_file():
            self.send_json({"error":"文件不存在"},404)
            return
        size=path.stat().st_size
        begin,end=0,size-1
        requested=self.headers.get("Range")
        if requested:
            match=re.fullmatch(r"bytes=(\d*)-(\d*)", requested)
            if not match or not any(match.groups()):
                self.send_response(416); self.send_header("Content-Range",f"bytes */{size}"); self.end_headers(); return
            a,b=match.groups()
            if a:
                begin=int(a); end=min(int(b),end) if b else end
            else:
                begin=max(0,size-int(b))
            if begin>=size or begin>end:
                self.send_response(416); self.send_header("Content-Range",f"bytes */{size}"); self.end_headers(); return
        self.send_response(206 if requested else 200)
        mime=mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        self.send_header("Content-Type",mime+("; charset=utf-8" if mime.startswith("text/") or mime in ("application/javascript","application/json") else ""))
        self.send_header("Accept-Ranges","bytes")
        self.send_header("Content-Length",str(end-begin+1))
        self.send_header("Cache-Control","no-cache")
        if requested:
            self.send_header("Content-Range",f"bytes {begin}-{end}/{size}")
        self.end_headers()
        with path.open("rb") as f:
            f.seek(begin)
            remaining=end-begin+1
            while remaining>0:
                block=f.read(min(1024*1024,remaining))
                if not block:break
                self.wfile.write(block)
                remaining-=len(block)

    def do_POST(self):
        if not self.local_request():
            self.send_json({"error":"请从本机实验台提交请求。"},403)
            return
        route=urlparse(self.path).path
        try:
            if route=="/api/upload":
                query=parse_qs(urlparse(self.path).query)
                name=query.get("name",["video.mp4"])[0]
                suffix=Path(name).suffix.lower()
                if suffix not in (".mp4",".mov",".mkv",".avi",".webm",".m4v"):
                    raise ValueError("支持 MP4、MOV、MKV、AVI、WEBM 视频。")
                total=int(self.headers.get("Content-Length",0))
                if total<=0 or total>200*1024**3:raise ValueError("视频大小无效。")
                path=MEDIA/(uuid.uuid4().hex+suffix)
                try:
                    with path.open("wb") as out:
                        remaining=total
                        while remaining:
                            block=self.rfile.read(min(2*1024*1024,remaining))
                            if not block:raise ValueError("视频传输中断。")
                            out.write(block);remaining-=len(block)
                    meta=add_video(path)
                    meta["original_name"]=name
                    self.send_json(meta)
                except Exception:
                    path.unlink(missing_ok=True)
                    raise
                return
            body=self.json_body()
            if route=="/api/video":
                self.send_json(add_video(body.get("path") or SAMPLE))
            elif route=="/api/jobs":
                kind=body.get("kind","analyze")
                if kind not in ("analyze","audio","proxy"):raise ValueError("任务类型无效。")
                meta=VIDEOS.get(body.get("video_id"))
                if not meta:raise ValueError("请先导入视频。")
                self.send_json(start_job(kind,meta,body.get("options",{})))
            elif route.startswith("/api/jobs/") and route.endswith("/cancel"):
                identity=route.split("/")[-2]
                if identity in JOBS:JOBS[identity][1].set()
                self.send_json({"ok":True})
            elif route=="/api/export":
                kind=body.get("kind")
                if kind not in ("html","json","csv"):raise ValueError("导出类型无效。")
                content=body.get("content")
                if not isinstance(content,str):raise ValueError("导出内容无效。")
                label=re.sub(r"[^\w\-\u4e00-\u9fff]","_",body.get("name","实验结果"))[:70]
                filename=f"{label}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:4]}.{kind}"
                path=EXPORTS/filename
                path.write_text(content,encoding="utf-8-sig" if kind=="csv" else "utf-8")
                self.send_json({"path":str(path),"url":"/exports/"+filename})
            else:
                self.send_json({"error":"接口不存在。"},404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception as exc:
            self.send_json({"error":str(exc)},400)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--port",type=int,default=8765)
    parser.add_argument("--open",action="store_true")
    args=parser.parse_args()
    port = args.port
    server = None
    ports = range(args.port, min(args.port+21, 65536)) if args.open else [args.port]
    for port in ports:
        try:
            server=LocalHTTPServer(("127.0.0.1",port),Handler)
            break
        except OSError:
            if not args.open:
                raise SystemExit(f"端口 {port} 已被占用，请更换 --port。")
            try:
                with urlopen(f"http://127.0.0.1:{port}/api/config", timeout=1) as response:
                    running=json.load(response)
                if running.get("root")==str(ROOT) and running.get("version")=="1.3":
                    print(f"此实验目录的服务已运行：http://127.0.0.1:{port}",flush=True)
                    webbrowser.open(f"http://127.0.0.1:{port}")
                    return
            except Exception:
                pass
    if server is None:
        raise SystemExit("未找到可用端口，请关闭占用服务或指定其他 --port。")
    print(f"Michelson Lab: http://127.0.0.1:{port}",flush=True)
    print(f"Output: {ROOT}",flush=True)
    if args.open:webbrowser.open(f"http://127.0.0.1:{port}")
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        for _,cancel in JOBS.values():cancel.set()
        server.server_close()
        POOL.shutdown(wait=False,cancel_futures=True)


if __name__=="__main__":main()
