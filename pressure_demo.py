"""Demo 01 的模拟压力数据。没有连接或读取真实硬件。"""

import asyncio
import csv
import html
import math
import random
import time
from datetime import datetime
from pathlib import Path

FIELDS = ("elapsed_s", "pressure_adc", "source", "scenario")


def simulate_pressure(elapsed_s, rng, manual_value=None):
    """返回模拟的 12 位 ADC 数字，不代表牛顿、千帕或真实传感器读数。"""
    if manual_value is None:
        # 自动演示：前 3 秒松开、3–7 秒按压，之后松开。
        target = 2400 if 3 <= elapsed_s < 7 else 300
    else:
        target = float(manual_value)
    return max(0, min(4095, round(target + rng.gauss(0, 12))))


async def collect_pressure(duration_s=10, sample_hz=20, manual_reader=None,
                           on_update=None, should_stop=None, records=None,
                           realtime=True):
    """逐条产生模拟数据；异步等待让 Notebook 能响应滑块和停止按钮。"""
    if not math.isfinite(duration_s) or not 0 < duration_s <= 120:
        raise ValueError('Capture duration must be between 0 and 120 seconds.')
    if not math.isfinite(sample_hz) or not 0 < sample_hz <= 100:
        raise ValueError('Sampling frequency must be between 0 and 100 Hz.')
    if duration_s * sample_hz < 1:
        raise ValueError('The current duration and frequency are insufficient to generate one sample.')
    rows = records if records is not None else []
    rng = random.Random(42)
    start = time.perf_counter()
    scenario = "manual" if manual_reader is not None else "automatic"
    update_every = max(1, round(sample_hz / 2))
    for i in range(math.ceil(duration_s * sample_hz)):
        nominal_time = i / sample_hz
        if realtime:
            await asyncio.sleep(max(0, start + nominal_time - time.perf_counter()))
        if should_stop and should_stop():
            break
        elapsed = time.perf_counter() - start if realtime else nominal_time
        value = manual_reader() if manual_reader else None
        rows.append({
            "elapsed_s": round(elapsed, 4),
            "pressure_adc": simulate_pressure(elapsed, rng, value),
            "source": "SIMULATED",
            "scenario": scenario,
        })
        if on_update and (i % update_every == 0):
            on_update(rows)
    if on_update:
        on_update(rows)
    return rows


def save_csv(rows, output_dir="data"):
    """带来源标记保存 CSV；每次生成独立文件，避免覆盖上次采集。"""
    if not rows:
        raise ValueError('No data yet. Run the capture step first.')
    folder = Path(output_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'pressure_SIMULATED_{datetime.now():%Y%m%d_%H%M%S_%f}.csv'
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path.resolve()


def preview_html(rows, limit=5):
    labels = ('Time (s)', 'Simulated ADC count', 'Data source', 'Demo mode')
    header = "".join(f'<th>{label}</th>' for label in labels)
    body = "".join("<tr>" + "".join(
        f'<td>{html.escape(str(row[field]))}</td>' for field in FIELDS
    ) + "</tr>" for row in rows[:limit])
    return f'<table><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>'

