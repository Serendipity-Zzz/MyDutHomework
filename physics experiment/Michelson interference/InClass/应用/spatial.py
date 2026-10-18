"""Local spatial-carrier phase tracking. Never uses pressure or reference wavelength to count."""
from __future__ import annotations

import math
import subprocess
import tempfile
import numpy as np
from scipy import ndimage

from analyzer import executable, interval, read_exact, CREATE_FLAGS


def carrier_candidate(block, times, rect, channel, background_sigma=4):
    size = block.shape[1]
    taper = np.outer(np.hanning(size), np.hanning(size))
    # Remove beam envelope/coarse grid spatially. No assumed temporal period.
    detail = block - ndimage.gaussian_filter(block, sigma=(0, background_sigma, background_sigma))
    transform = np.fft.fft2(detail * taper, axes=(1, 2))
    power = np.mean(np.abs(transform) ** 2, axis=0)
    freq = np.fft.fftfreq(size)
    kx, ky = np.meshgrid(freq, freq)
    mask = (kx > .045) & (kx < .43) & (np.hypot(kx, ky) < .46) & (np.abs(ky) < .36)
    energy = float(np.sum(power[mask]))
    if energy < 1e-6:
        return None
    row, column = np.unravel_index(np.argmax(np.where(mask, power, 0)), power.shape)
    z = transform[:, row, column]
    amplitude = np.abs(z)
    phase = np.unwrap(np.angle(z)) / (2 * np.pi)
    phase -= float(np.median(phase[:5]))
    if np.median(phase[-5:]) < 0:
        phase *= -1
    smoothed = ndimage.median_filter(phase, size=3, mode="nearest")
    strength = float(np.median(amplitude) / np.sum(taper))
    concentration = float(power[row, column] / energy)
    floor = float(np.percentile(amplitude, 10) / (np.median(amplitude) + 1e-9))
    variation = float(np.sum(np.abs(np.diff(phase))))
    net = float(np.median(phase[-5:]) - np.median(phase[:5]))
    directed_fraction = abs(net) / (variation + 1e-9)
    score = strength * concentration * floor * directed_fraction
    if not math.isfinite(score) or strength < .3:
        return None
    return {"channel": channel, "rect": rect, "carrier": [float(freq[column]), float(freq[row])],
            "phase": smoothed, "raw_phase": phase, "complex": z,
            "score": score, "strength": strength, "concentration": concentration,
            "contrast_floor": floor, "net": net, "directed_fraction": directed_fraction}


def summarize_candidates(times, candidates, prefer_terminal_branch=True):
    """Find terminal monotonic branch from image phase alone, not from a target ring count."""
    if not candidates:
        raise ValueError("未找到足够清晰的空间细纹，请扩大选区或切换亮度峰值法。")
    candidates.sort(key=lambda c: c["score"], reverse=True)
    best = candidates[0]
    pool = [c for c in candidates[:20]
            if c["score"] >= best["score"] * .12 and c["contrast_floor"] > .25]
    # Use strong patches, not all illuminated pixels; phase sign is a drawing convention.
    pool = pool[:8]
    phase0 = best["phase"]
    smooth = ndimage.gaussian_filter1d(phase0, sigma=1)
    min_index = int(np.argmin(smooth))
    near_min = np.flatnonzero(smooth[:max(min_index+1, len(smooth)-4)] <= smooth[min_index] + .04)
    start_index = int(near_min[-1]) if len(near_min) else min_index
    # A strictly monotonic recording starts at its first frame; no arbitrary loss of early motion.
    if smooth[min_index] > -.15:
        start_index = 0
    if not prefer_terminal_branch:
        start_index = 0
    if start_index >= len(times) - 8:
        raise ValueError("画面末段没有可追踪的连续变化，请手动指定测量时间段。")
    for c in pool:
        c["release_count"] = float(c["phase"][-1] - c["phase"][start_index])
    midpoint = float(np.median([c["release_count"] for c in pool]))
    consistent = [c for c in pool if abs(c["release_count"] - midpoint) <= max(.55, abs(midpoint)*.08)]
    if len(consistent) < 2:
        consistent = pool[:1]
    aligned = np.asarray([c["phase"] - c["phase"][start_index] for c in consistent])
    combined = np.median(aligned, axis=0)
    count = float(combined[-1] - combined[start_index])
    spread = float(np.ptp([c["release_count"] for c in consistent]))
    phase_steps = np.abs(np.diff(combined[start_index:]))
    max_step = float(np.max(phase_steps)) if len(phase_steps) else 0
    warnings = ["空间相位给出候选条纹量；相位符号不直接对应物理上的吞/吐，结果仍需原视频校核。"]
    if prefer_terminal_branch:
        warnings.append("区间起点根据画面相位的反向/停顿识别，不是压力表读数；默认终点为视频结尾附近。")
    else:
        warnings.append("波长实验保留输入时间段，不套用放气末段裁剪；声音候选需按实际转动读数核对。")
    reversal = bool(start_index > 0 and smooth[min_index] < -.15)
    if reversal:
        warnings.append(f"视频前段含反向变化，建议只使用 {times[start_index]:.2f} 秒之后的末段；前段不合并为放气计数。")
    if max_step > .40:
        warnings.append("部分帧间相位变化接近半周期，存在采样不足或相位展开漏圈风险。")
    if len(consistent) < 3 or spread > .5:
        warnings.append("清晰区域数量或区域间一致性不足，计数需人工复核。")
    if count < 1:
        warnings.append("末段变化不足一个周期，不适合作为完整测量。")
    return {"phase": combined - combined[0], "count": abs(count), "start_index": start_index,
            "spread": spread, "max_step": max_step, "consistent": consistent, "pool": pool,
            "warnings": warnings, "reversal": reversal,
            "needs_review": len(consistent)<3 or spread>.5 or max_step>.40 or count<1}


def analyze_spatial(meta, options, progress, cancelled):
    start, end = interval(meta, options)
    roi = list(map(float, options.get("roi", [.25,.22,.65,.45])))
    if len(roi) != 4 or not all(math.isfinite(v) for v in roi):
        raise ValueError("选区无效。")
    rx,ry,rw,rh = roi
    if rx<0 or ry<0 or rw<=0 or rh<=0 or rx+rw>1.001 or ry+rh>1.001:
        raise ValueError("选区必须位于画面内。")
    x,y = int(rx*meta["width"]),int(ry*meta["height"])
    w,h = min(int(rw*meta["width"]),meta["width"]-x),min(int(rh*meta["height"]),meta["height"]-y)
    if min(w,h)<32:
        raise ValueError("空间相位法的选区至少需 32×32 像素，请框选一片清晰细纹。")
    scale = min(1, 360/max(w,h))
    sw,sh = max(32,int(w*scale)),max(32,int(h*scale))
    if (end-start)*meta["fps"]*sw*sh*3*2 > 768*1024**2:
        raise ValueError("当前区间的空间相位分析内存需求较大，请先截取单次实验的较短时间段，或缩小选区。")
    cmd = [executable("ffmpeg"),"-v","error","-ss",str(start),"-i",meta["path"],"-t",str(end-start),
           "-an","-vf",f"fps={meta['fps']:.9f},crop={w}:{h}:{x}:{y},scale={sw}:{sh}:flags=area",
           "-pix_fmt","rgb24","-f","rawvideo","pipe:1"]
    frames=[]
    with tempfile.TemporaryFile() as err:
        proc=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=err,creationflags=CREATE_FLAGS)
        try:
            while True:
                if cancelled():raise ValueError("分析已取消。")
                block=read_exact(proc.stdout,sw*sh*3)
                if len(block)<sw*sh*3:break
                frames.append(np.frombuffer(block,dtype=np.uint8).reshape((sh,sw,3)).copy())
                if len(frames)%30==0:progress(min(.45,.45*len(frames)/meta["fps"]/(end-start)),f"正在读取细纹第 {len(frames)} 帧")
            if proc.wait():
                err.seek(0);raise ValueError("视频解码失败："+err.read().decode("utf-8","replace")[-300:])
        finally:
            if proc.poll() is None:proc.kill()
            proc.wait()
    if len(frames)<16:raise ValueError("有效帧数不足。")
    frames=np.asarray(frames)
    times=start+np.arange(len(frames))/meta["fps"]
    # Memory is bounded for long input by asking the caller to select a trial segment.
    size=int(options.get("spatial_window",32))
    sigma=float(options.get("spatial_sigma",4))
    if size not in (16,24,32,48,64) or not 1<=sigma<=8:
        raise ValueError("空间窗口应选16/24/32/48/64像素，背景尺度应在1到8像素。")
    if min(sw,sh)<size:
        raise ValueError("选区小于空间窗口，请扩大选区或减小窗口。")
    channel=options.get("channel","auto")
    choices=[("G",1),("R",0)] if channel=="auto" else [(channel,{"R":0,"G":1,"B":2,"Y":1}.get(channel,1))]
    step=max(8,size//2)
    rectangles=[(xx,yy) for yy in range(0,sh-size+1,step) for xx in range(0,sw-size+1,step)]
    candidates=[]
    for ci,(name,index) in enumerate(choices):
        for ri,(xx,yy) in enumerate(rectangles):
            if cancelled():raise ValueError("分析已取消。")
            if name == "Y":
                block=frames[:,yy:yy+size,xx:xx+size,:].astype(np.float32) @ np.asarray([.2126,.7152,.0722],dtype=np.float32)
            else:
                block=frames[:,yy:yy+size,xx:xx+size,index].astype(np.float32)
            rect=[x+xx*w/sw,y+yy*h/sh,size*w/sw,size*h/sh]
            candidate=carrier_candidate(block,times,rect,name,background_sigma=sigma)
            if candidate:candidates.append(candidate)
            if ri%12==0:
                progress(.45+.5*(ci*len(rectangles)+ri)/(len(choices)*len(rectangles)),"正在比较局部细纹的空间相位")
    summary=summarize_candidates(times,candidates,prefer_terminal_branch=options.get("experiment","air")=="air")
    selected=summary["consistent"][0]
    # Bright maxima crossings on the recommended monotonic branch, only for video navigation.
    phase=summary["phase"]
    si=summary["start_index"]
    forward=phase[si:]-phase[si]
    crossing_times=[]
    for level in range(1,int(summary["count"])+1):
        found=np.flatnonzero((forward[:-1]<level)&(forward[1:]>=level))
        if len(found):
            j=int(found[0])+si
            crossing_times.append(float(times[j]+(level-(phase[j]-phase[si]))/(phase[j+1]-phase[j])*(times[j+1]-times[j])))
    records=[]
    for i,c in enumerate(summary["pool"]):
        records.append({"channel":c["channel"],"patch":i+1,"complete_cycles":int(max(0,c["release_count"])),
                        "phase_count":c["release_count"],"score":c["score"],"amplitude":c["strength"],
                        "dominant_hz":0,"rect":c["rect"],"carrier":c["carrier"],
                        "contrast_floor":c["contrast_floor"]})
    raw=np.real(selected["complex"])/(np.median(np.abs(selected["complex"]))+1e-9)
    return {"method":"spatial","times":times.tolist(),"raw":raw.tolist(),"signal":phase.tolist(),
            "phase_cycles":phase.tolist(),"peaks":crossing_times,"peak_values":[],
            "complete_cycles":int(summary["count"]),"phase_count":summary["count"],
            "valid_range":[float(times[0]),float(times[-1])],
            "recommended_range":[float(times[si]),float(times[-1])],
            "recommended_start_reason":"terminal_phase_branch" if summary["reversal"] else "full_interval",
            "channel":selected["channel"],"patch":1,"selected_rect":selected["rect"],
            "carrier":selected["carrier"],"score":selected["score"],"amplitude":selected["strength"],
            "patch_count":len(summary["consistent"]),"patch_spread":summary["spread"],
            "max_phase_step":summary["max_step"],"needs_review":summary["needs_review"],
            "warnings":summary["warnings"],"candidates":records,"roi":roi,"fps":meta["fps"],
            "frame_count":len(times),"start":start,"end":end,"source":"video_auto","options":options,
            "timing_note":meta["timing_note"]}
