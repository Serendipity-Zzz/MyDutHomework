"""Offline Michelson video/audio processing. No cloud services or speech model required."""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
from typing import Callable

import numpy as np
from scipy import signal, ndimage

CREATE_FLAGS = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def executable(name):
    found = shutil.which(name)
    if not found:
        raise ValueError(f"找不到 {name}，请安装 FFmpeg 并加入 PATH。")
    return found


def run(args, **kwargs):
    return subprocess.run(args, creationflags=CREATE_FLAGS, **kwargs)


def probe(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise ValueError("视频文件不存在，请检查完整路径。")
    proc = run([executable("ffprobe"), "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)], capture_output=True, timeout=45)
    if proc.returncode:
        raise ValueError("无法读取视频：" + proc.stderr.decode("utf-8", "replace")[-600:])
    data = json.loads(proc.stdout)
    video = next((s for s in data["streams"] if s["codec_type"] == "video" and not s.get("disposition", {}).get("attached_pic")), None)
    if video is None:
        raise ValueError("该文件没有视频流。")
    def rate(value):
        try:
            a, b = value.split("/")
            return float(a) / float(b)
        except (ValueError, ZeroDivisionError):
            return 0
    duration = float(data.get("format", {}).get("duration", video.get("duration", 0)))
    fps = rate(video.get("avg_frame_rate", "0/1")) or rate(video.get("r_frame_rate", "30/1"))
    if duration <= 0 or not 0 < fps <= 1000:
        raise ValueError("视频时长或帧率无效。")
    rotation = next((int(s.get("rotation", 0)) for s in video.get("side_data_list", []) if "rotation" in s), 0)
    width, height = int(video["width"]), int(video["height"])
    if abs(rotation) % 180 == 90:
        width, height = height, width
    return {"path": str(path), "name": path.name, "duration": duration, "fps": fps,
            "width": width, "height": height, "codec": video["codec_name"],
            "size": path.stat().st_size, "audio": any(s["codec_type"] == "audio" for s in data["streams"]),
            "timing_note": "按视频平均帧率统一到等时间间隔；声音使用同一原视频时间轴。"}


def interval(meta, options):
    start = float(options.get("start", 0))
    end = float(options.get("end") or meta["duration"])
    if not math.isfinite(start + end) or start < 0 or end > meta["duration"] + .05 or end <= start:
        raise ValueError("分析区间须满足 0 ≤ 起点 < 终点 ≤ 视频时长。")
    return start, min(end, meta["duration"])


def detect_cycles(times, values, max_hz=5.0, prominence=.65):
    """Peak-to-peak counting; arbitrary endpoints are interpolated ONLY inside peak support."""
    t = np.asarray(times, dtype=float)
    raw = np.asarray(values, dtype=float)
    if len(t) < 16 or len(raw) != len(t):
        raise ValueError("有效帧数不足，至少需要 16 帧。")
    fs = 1 / float(np.median(np.diff(t)))
    max_hz = min(float(max_hz), fs / 4)
    if max_hz <= .05 or not 0.1 <= float(prominence) <= 4:
        raise ValueError("计数频率或显著度参数无效。")
    # Median baseline suppresses exposure drift; no assumed reference wavelength is used.
    window = min(len(raw) // 2 * 2 - 1, max(7, int(fs * 4) // 2 * 2 + 1))
    baseline = ndimage.median_filter(raw, size=window, mode="nearest")
    detrended = raw - baseline
    smooth_window = max(3, int(fs / max_hz / 3) // 2 * 2 + 1)
    smooth_window = min(smooth_window, len(raw) // 2 * 2 - 1)
    smoothed = signal.savgol_filter(detrended, smooth_window, min(2, smooth_window - 1))
    scale = float(np.percentile(smoothed, 90) - np.percentile(smoothed, 10))
    noise = float(np.median(np.abs(np.diff(smoothed))) / .6745 / math.sqrt(2))
    if scale < .05:
        peaks = np.array([], dtype=int)
    else:
        threshold = max(.04, scale * float(prominence) * .32)
        peaks, _ = signal.find_peaks(smoothed, prominence=threshold, distance=max(2, int(fs / max_hz)))
    f, power = signal.periodogram(smoothed, fs)
    band = (f >= max(.08, 1 / (t[-1] - t[0]))) & (f <= max_hz)
    total = float(power[band].sum())
    dominant = float(f[band][np.argmax(power[band])]) if total > 0 else 0
    concentration = float(power[band].max() / total) if total > 0 else 0
    pt = t[peaks]
    periods = np.diff(pt)
    cv = float(np.std(periods) / np.mean(periods)) if len(periods) >= 2 else 1
    # This is a screening score, NOT a probability of correct fringe counting.
    score = concentration * math.log1p(max(scale, 0)) / (1 + min(cv, 3)) if len(peaks) >= 3 else 0
    warnings = []
    if len(peaks) < 3:
        warnings.append("完整周期不足，请重新选择区域、时间段，或使用人工条纹数。")
    if scale < 1:
        warnings.append("亮度变化较弱，压缩噪声或曝光变化可能影响计数。")
    if cv > .4 and len(periods) >= 3:
        warnings.append("周期时长不均匀；可能存在调速、停顿或漏计，需回放核查。")
    if dominant > fs / 8:
        warnings.append("条纹变化较快，每周期采样点偏少。")
    observed_hz = (len(pt)-1)/(pt[-1]-pt[0]) if len(pt)>=2 else 0
    if observed_hz and dominant and max(observed_hz/dominant,dominant/observed_hz)>2.5:
        warnings.append("峰值计数速度与主要亮度频率不一致，可能将噪声计为周期，需人工核查。")
    return {"raw": raw.tolist(), "signal": smoothed.tolist(), "peaks": pt.tolist(),
            "peak_values": smoothed[peaks].tolist(), "complete_cycles": max(0, len(pt) - 1),
            "valid_range": [float(pt[0]), float(pt[-1])] if len(pt) >= 2 else None,
            "score": score, "amplitude": scale, "noise_estimate": noise,
            "dominant_hz": dominant, "period_cv": cv, "warnings": warnings}


def read_exact(stream, count):
    out = bytearray()
    while len(out) < count:
        chunk = stream.read(count - len(out))
        if not chunk:
            break
        out.extend(chunk)
    return out


def audio_onsets(meta, options, progress, cancelled):
    if not meta["audio"]:
        return {"times": [], "envelope": [], "markers": [], "warnings": ["视频没有音轨，可手动添加时间标记。"]}
    start, end = interval(meta, options)
    sensitivity = float(options.get("audio_sensitivity", 1))
    gap = float(options.get("audio_gap", .6))
    if not .25 <= sensitivity <= 4 or not .1 <= gap <= 10:
        raise ValueError("声音检测参数超出范围。")
    cmd = [executable("ffmpeg"), "-v", "error", "-ss", str(start), "-i", meta["path"], "-t", str(end-start),
           "-vn", "-ac", "1", "-ar", "8000", "-f", "f32le", "pipe:1"]
    times, env = [], []
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, creationflags=CREATE_FLAGS)
        try:
            while True:
                if cancelled():
                    raise ValueError("分析已取消。")
                block = read_exact(proc.stdout, 160 * 4)
                if len(block) < 160 * 4:
                    break
                x = np.frombuffer(block, dtype="<f4")
                times.append(start + len(env) * .02)
                env.append(float(np.sqrt(np.mean(x*x))))
                if len(env) % 500 == 0:
                    progress(min(.95, len(env)*.02/(end-start)), "正在检测声音起点")
            code = proc.wait()
            if code:
                err.seek(0)
                raise ValueError("音轨解码失败：" + err.read().decode("utf-8", "replace")[-300:])
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
    if not env:
        return {"times": [], "envelope": [], "markers": [], "warnings": ["未读到有效音频。"]}
    smooth = ndimage.uniform_filter1d(np.asarray(env), size=5)
    floor = float(np.percentile(smooth, 20))
    mad = float(np.median(np.abs(smooth - np.median(smooth))))
    threshold = max(1e-4, floor + max(2.5*mad, (float(np.percentile(smooth, 95))-floor)*.2)*sensitivity)
    active = smooth > threshold
    # Merge syllables and short pauses into one utterance.
    spans = []
    indices = np.flatnonzero(active)
    if len(indices):
        first = last = int(indices[0])
        for index in indices[1:]:
            if (index-last)*.02 > gap:
                if (last-first+1)*.02 >= .10:
                    spans.append((first, last))
                first = int(index)
            last = int(index)
        if (last-first+1)*.02 >= .10:
            spans.append((first,last))
    markers = [{"time": round(times[a], 3), "end": round(times[b]+.02, 3), "enabled": True,
                "source": "audio_candidate", "label": f"声音 {i+1}"} for i,(a,b) in enumerate(spans)]
    return {"times": times, "envelope": env, "threshold": threshold, "markers": markers,
            "warnings": ["声音检测只定位声段起点，不识别说话内容；请回听剔除环境声和重复报数。"]}


def analyze_video(meta, options, progress, cancelled):
    if options.get("method") == "spatial":
        from spatial import analyze_spatial
        return analyze_spatial(meta, options, progress, cancelled)
    start, end = interval(meta, options)
    roi = options.get("roi", [.4,.4,.2,.15])
    if len(roi) != 4 or any(not math.isfinite(float(v)) for v in roi):
        raise ValueError("选区无效。")
    rx,ry,rw,rh = map(float, roi)
    if rx < 0 or ry < 0 or rw <= 0 or rh <= 0 or rx+rw > 1.001 or ry+rh > 1.001:
        raise ValueError("选区必须位于视频画面内。")
    x,y = int(rx*meta["width"]), int(ry*meta["height"])
    w,h = max(2,int(rw*meta["width"])),max(2,int(rh*meta["height"]))
    w,h = min(w,meta["width"]-x),min(h,meta["height"]-y)
    max_hz = float(options.get("max_hz", 5))
    prominence = float(options.get("prominence", .65))
    if not .1 <= max_hz <= 60 or not .1 <= prominence <= 4:
        raise ValueError("检测参数超出范围。")
    # Spatial reduction only; all time samples retained at avg_frame_rate (also supports VFR input).
    cmd = [executable("ffmpeg"), "-v", "error", "-ss", str(start), "-i", meta["path"], "-t", str(end-start),
           "-an", "-vf", f"fps={meta['fps']:.9f},crop={w}:{h}:{x}:{y},scale=96:96:flags=area", "-pix_fmt", "rgb24", "-f", "rawvideo", "pipe:1"]
    # Whole ROI and 3x3 subregions, each RGB + luminance, tracked independently.
    rectangles = [(0,0,96,96)] + [(a*32,b*32,32,32) for b in range(3) for a in range(3)]
    samples = []
    clip_fractions = []
    with tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err, creationflags=CREATE_FLAGS)
        try:
            while True:
                if cancelled():
                    raise ValueError("分析已取消。")
                block = read_exact(proc.stdout,96*96*3)
                if len(block) < 96*96*3:
                    break
                frame = np.frombuffer(block,dtype=np.uint8).reshape((96,96,3))
                values = []
                for a,b,c,d in rectangles:
                    patch = frame[b:b+d,a:a+c]
                    rgb = patch.mean(axis=(0,1))
                    values.extend([*rgb,float(rgb @ [.2126,.7152,.0722])])
                samples.append(values)
                if len(samples) % 30 == 0:
                    clip_fractions.append(float(np.mean(frame>=250)))
                    progress(min(.96,len(samples)/meta["fps"]/(end-start)), f"正在读取第 {len(samples)} 帧")
            code = proc.wait()
            if code:
                err.seek(0)
                raise ValueError("视频解码失败："+err.read().decode("utf-8","replace")[-500:])
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
    times = start + np.arange(len(samples))/meta["fps"]
    matrix = np.asarray(samples)
    if len(matrix) < 16:
        raise ValueError("区间过短或视频无有效帧，请扩大时间段。")
    channel = options.get("channel","auto")
    channels = {"R":0,"G":1,"B":2,"Y":3}
    allowed = range(matrix.shape[1]) if channel == "auto" else [i for i in range(matrix.shape[1]) if i%4 == channels.get(channel,3)]
    candidates = []
    for i in allowed:
        result = detect_cycles(times,matrix[:,i],max_hz,prominence)
        result.update({"column":i,"channel":["R","G","B","Y"][i%4],"patch":i//4})
        candidates.append(result)
    candidates.sort(key=lambda c:c["score"],reverse=True)
    best = candidates[0]
    peers = [c for c in candidates[:8] if c["score"] > best["score"]*.3 and c["complete_cycles"]>0]
    counts = [c["complete_cycles"] for c in peers]
    best["warnings"].append("自动结果是候选计数；局部区域采用近轴近似，须结合原视频核查，不能识别反向转动。")
    if counts and max(counts)-min(counts) > max(2,np.median(counts)*.12):
        best["warnings"].append("多个区域的候选计数差异较大，建议缩小选区或手动修正。")
    if clip_fractions and np.mean(clip_fractions)>.05:
        best["warnings"].append("选区存在亮度接近饱和的像素。")
    needs_review = len(best["peaks"])<3 or best["amplitude"]<1 or any("差异较大" in warning or "不一致" in warning for warning in best["warnings"])
    return {"times":times.tolist(), **best, "needs_review":needs_review, "roi":roi, "fps":meta["fps"],
            "frame_count":len(times), "start":start,"end":end,
            "candidates":[{k:c[k] for k in ("channel","patch","complete_cycles","score","amplitude","dominant_hz")} for c in candidates[:8]],
            "options":options,"source":"video_auto"}


def make_proxy(meta, destination, progress, cancelled):
    destination = Path(destination)
    temporary = destination.with_name(destination.stem + ".partial.mp4")
    cmd=[executable("ffmpeg"),"-hide_banner","-v","error","-y","-i",meta["path"],"-vf","scale='min(960,iw)':-2",
         "-c:v","libx264","-preset","veryfast","-crf","23","-pix_fmt","yuv420p","-c:a","aac","-b:a","96k",
         "-movflags","+faststart","-progress","pipe:1",str(temporary)]
    with tempfile.TemporaryFile() as err:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err,creationflags=CREATE_FLAGS)
        try:
            for line in iter(proc.stdout.readline,b""):
                if cancelled():
                    raise ValueError("转码已取消。")
                text=line.decode("utf-8","replace").strip()
                if text.startswith("out_time_us="):
                    progress(min(.99,float(text.split("=",1)[1])/1e6/meta["duration"]),"正在生成兼容预览，计算仍使用原视频")
            if proc.wait():
                err.seek(0)
                raise ValueError("转码失败："+err.read().decode("utf-8","replace")[-500:])
        finally:
            if proc.poll() is None:
                proc.kill()
            proc.wait()
            if cancelled() or proc.returncode:
                temporary.unlink(missing_ok=True)
    temporary.replace(destination)
    return str(destination)
