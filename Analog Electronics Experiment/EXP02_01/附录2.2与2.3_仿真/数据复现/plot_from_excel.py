"""Read the submitted Excel workbook and reproduce the appendix figures.

Requires Python 3, openpyxl, numpy and matplotlib.
Run from any directory. The workbook is beside this script.
"""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent
BOOK = ROOT / 'EXP02_01_RGXXXX_STUDENT_ID.xlsx'
OUT = Path(__file__).resolve().parent.parent / '截图'
OUT.mkdir(exist_ok=True)
wb = load_workbook(BOOK, data_only=True, read_only=True)

def read_points(sheet, xcol, ycol):
    points = [(r[xcol], r[ycol]) for r in wb[sheet].iter_rows(
        min_row=2, values_only=True) if isinstance(r[xcol], (int, float))
        and isinstance(r[ycol], (int, float))]
    points.sort(key=lambda p: p[0])
    return np.asarray(points, dtype=float).T

sim_x, sim_y = read_points('仿真数据', 2, 3)
obs_x, obs_y = read_points('实测整理', 3, 4)
assert len(sim_x) == 337 and len(obs_x) == 51
font = Path('C:/Windows/Fonts/msyh.ttc')
if font.exists():
    font_manager.fontManager.addfont(str(font))
    plt.rcParams['font.family'] = font_manager.FontProperties(
        fname=str(font)).get_name()
plt.rcParams.update({'axes.unicode_minus': False, 'font.size': 10})

def draw(name, comparison=False, zoom=False):
    fig, ax = plt.subplots(figsize=(8.0, 4.0), layout='constrained')
    ax.plot(sim_x, sim_y, '-o', color='#245E91', markersize=2.1,
            linewidth=1.2, label='Altium 仿真')
    if comparison:
        ax.plot(obs_x, obs_y, '-s', color='#C46028', markersize=3.0,
                linewidth=1.0, label='课堂实测')
    ax.set(xlabel='二极管端电压 Ud / V', ylabel='二极管电流 Id / mA',
           xlim=(-6.25, -5.4) if zoom else (-7, 1),
           ylim=(-2.2, 0.15) if zoom else (-15, 20))
    ax.axhline(0, color='#888888', linewidth=0.6)
    ax.axvline(0, color='#888888', linewidth=0.6)
    ax.grid(True, color='#D9D9D9', linewidth=0.6)
    ax.legend(loc='upper left', frameon=False)
    title = '反向击穿拐点局部对照' if zoom else (
        '仿真与实测伏安特性对照' if comparison else 'Altium 仿真伏安特性')
    ax.set_title(title, fontsize=11, pad=10)
    fig.savefig(OUT / name, dpi=240)
    plt.close(fig)

draw('Python_仿真曲线.png')
draw('Python_仿真实测对照.png', comparison=True)
draw('Python_反向拐点.png', comparison=True, zoom=True)
wb.close()
print(f'Generated three figures from {BOOK.name}')
