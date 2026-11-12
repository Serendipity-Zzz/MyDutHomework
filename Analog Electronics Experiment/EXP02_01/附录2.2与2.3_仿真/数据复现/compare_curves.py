"""Reproduce the audited plots from Altium SDF and the recorded measurements.

Run this file with Python, NumPy and Matplotlib. Paths are resolved from the
project directory, so the working directory can be chosen freely.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np


def read_sdf(path):
    data = Path(path).read_bytes()
    if not data.startswith(b'SDF: 1.0'):
        raise ValueError('Expected an Altium SDF 1.0 file.')
    waves = {}
    position = 0
    chart = ''
    while position < len(data):
        end = data.find(b'\n', position)
        if end < 0:
            break
        line = data[position:end].decode('cp1252', errors='replace').strip()
        position = end + 1
        if line.startswith('Chart:'):
            chart = line.split(':', 1)[1].strip()
        if not line.startswith('Wave:'):
            continue
        name = line.split(':', 1)[1].strip().lower()
        header = {}
        while True:
            end = data.find(b'\n', position)
            if end < 0:
                raise ValueError(f'Truncated header for {name}.')
            line = data[position:end].decode('cp1252', errors='replace').strip()
            position = end + 1
            if line == 'WaveDataStart':
                break
            if ':' in line:
                key, value = line.split(':', 1)
                header[key] = value.strip()
        count = int(header['WavePoints'])
        if header.get('WaveIsXComplex') != 'FALSE' or header.get('WaveIsYComplex') != 'FALSE':
            raise ValueError('This DC analysis requires real-valued waveforms.')
        byte_count = count * 8
        if position + byte_count > len(data):
            raise ValueError(f'Truncated samples for {name}.')
        samples = np.frombuffer(data[position:position + byte_count], dtype='<f4').reshape(count, 2).astype(float)
        position += byte_count
        if 'dc' in chart.lower():
            order = np.argsort(samples[:, 0], kind='stable')
            samples = samples[order]
            if not np.all(np.isfinite(samples)):
                raise ValueError(f'Non-finite samples in {name}.')
            if np.any(np.diff(samples[:, 0]) <= 0):
                raise ValueError(f'Duplicate or invalid sweep coordinates in {name}.')
            waves[name] = {'uin_v': samples[:, 0], 'value': samples[:, 1]}
    return waves


def write_csv(path, fields, rows):
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(fields)
        writer.writerows(rows)


def independent_model_check(model_path, voltage_wave, current_wave):
    """Solve the supplied nominal-temperature SPICE diode DC equations."""
    model_text = model_path.read_text(encoding='ascii')
    values = {name.upper(): float(value) for name, value in re.findall(r'\b([A-Za-z]+)\s*=\s*([+-]?[\d.]+(?:[Ee][+-]?\d+)?)', model_text)}
    thermal_voltage = 8.617333262145e-5 * (273.15 + 27)
    emission_voltage = values.get('N', 1.0) * thermal_voltage
    saturation_current = values['IS']
    breakdown_adjusted = values['BV'] - emission_voltage * np.log(values['IBV'] / saturation_current)

    def calculate(inputs):
        lower = np.full_like(inputs, -7.0)
        upper = np.full_like(inputs, 1.0)
        for _ in range(90):
            junction_voltage = (lower + upper) / 2
            current = saturation_current * (
                np.expm1(junction_voltage / emission_voltage)
                - np.exp(-(junction_voltage + breakdown_adjusted) / emission_voltage)
            )
            residual = junction_voltage + (1000 + values['RS']) * current - inputs
            upper = np.where(residual > 0, junction_voltage, upper)
            lower = np.where(residual <= 0, junction_voltage, lower)
        junction_voltage = (lower + upper) / 2
        current = saturation_current * (
            np.expm1(junction_voltage / emission_voltage)
            - np.exp(-(junction_voltage + breakdown_adjusted) / emission_voltage)
        )
        return junction_voltage + values['RS'] * current, current * 1000

    predicted_voltage, _ = calculate(voltage_wave['uin_v'])
    _, predicted_current = calculate(current_wave['uin_v'])
    voltage_difference = np.max(np.abs(predicted_voltage - voltage_wave['value']))
    current_difference = np.max(np.abs(predicted_current - current_wave['value'] * 1000))
    if voltage_difference > 0.001 or current_difference > 0.001:
        raise ValueError('The saved waveforms differ materially from the supplied model equations.')
    return {
        'method': 'SPICE diode DC equations with the supplied model constants, 27 C and 1 kohm',
        'maximum_voltage_difference_v': float(voltage_difference),
        'maximum_current_difference_ma': float(current_difference),
        'model_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
    }


def save_iv_document(path, voltage, current):
    header = f'''SDF: 1.0
TotalPoints: {len(current)}
#ChartSetupsBegin
Chart: DC Sweep
ChartView: 4
ChartTitle: 1N4735A I-V - saved Altium current
ChartBackgroundColor: 16777215
ChartForegroundColor: 0
ChartGridColor: 14211288
ChartXDivisions: 9
ChartXOffset: 0
ChartXDivSize: 1
ChartXMin: -7
ChartXMax: 2
ChartAutoXMin: FALSE
ChartAutoXMax: FALSE
ChartAutoXDiv TRUE
ChartUseXDefaults: FALSE
ChartXDataType: 0
ChartPrimaryYDataType: 0
ChartXScaleMode: 0
ChartYScaleMode: 0
ChartBoldWaves: TRUE
ChartShowDataPoints: FALSE
ChartShowWaveSymbols: FALSE
ChartShowChartTitle: TRUE
ChartShowAxisLabels: TRUE
ChartFourier: FALSE
ChartTable: FALSE
ChartType: XY Scatter
ChartXUnitStr: V
ChartXLabel: Ud
Cell: 0
CellHeight: 520
CellIsScaled: TRUE
CellTitle Id versus Ud
CellXGrid: TRUE
CellYGrid: TRUE
CellMinorGrid: TRUE
CellAxisAutoMin: TRUE
CellAxisAutoMax: TRUE
CellAxisAutoDiv: TRUE
CellAxisAutoUnits: FALSE
CellAxisLabel: Id
CellAxisUnits: mA
WaveName: Id_mA
WaveEq: Id_mA
WaveColor: 11101224
WaveYUnitStr: mA
CellSelectedAxis: 0
ChartActiveCellIndex: 0
ChartTopCellIndex: 0
ActiveChartName: DC Sweep
#ChartSetupsEnd
Chart: DC Sweep
ChartXMinReal: {voltage.min():.14E}
ChartXMaxReal: {voltage.max():.14E}
Wave: Id_mA
WaveYUnitStr: mA
WaveHint: Original R1 current with Ud interpolated at its sweep coordinates
WavePoints: {len(current)}
WaveIsXComplex: FALSE
WaveIsYComplex: FALSE
WaveType: 0

WaveDataStart
'''
    path.write_bytes(header.encode('ascii') + np.column_stack([voltage, current]).astype('<f4').tobytes() + b'\n')


def main():
    project = Path(__file__).resolve().parent.parent
    data_directory = project / '数据复现'
    parser = argparse.ArgumentParser()
    parser.add_argument('--sdf', type=Path, default=Path('Altium/DC_Sweep.sdf'))
    arguments = parser.parse_args()
    sdf_path = arguments.sdf if arguments.sdf.is_absolute() else project / arguments.sdf
    waves = read_sdf(sdf_path)
    voltage_wave = waves['ud']
    current_wave = waves['r1[i]']
    check = independent_model_check(project / 'Altium/1N4735.mdl', voltage_wave, current_wave)

    # The simulation extraction below depends on the saved solver waves.
    sweep = current_wave['uin_v']
    simulated_current = current_wave['value'] * 1000
    simulated_voltage = np.interp(sweep, voltage_wave['uin_v'], voltage_wave['value'])
    kvl_current = sweep - simulated_voltage
    kvl_residual = kvl_current - simulated_current
    if np.max(np.abs(kvl_residual)) > 0.01:
        raise ValueError('The independently saved voltage and current fail the circuit KVL check.')
    write_csv(data_directory / 'raw_ud.csv', ['uin_v', 'ud_v'], zip(voltage_wave['uin_v'], voltage_wave['value']))
    write_csv(data_directory / 'raw_current.csv', ['uin_v', 'id_a', 'id_ma'], zip(sweep, current_wave['value'], simulated_current))
    write_csv(data_directory / 'simulation.csv', ['uin_v', 'ud_v', 'id_ma', 'kvl_id_ma', 'kvl_residual_ma'], zip(sweep, simulated_voltage, simulated_current, kvl_current, kvl_residual))
    save_iv_document(project / 'Altium/Zener_IV.sdf', simulated_voltage, simulated_current)

    with (data_directory / 'measured.csv').open(encoding='utf-8-sig', newline='') as stream:
        measured = list(csv.DictReader(stream))
    measured_uin = np.array([float(row['uin_v']) for row in measured])
    measured_voltage = np.array([float(row['ud_v']) for row in measured])
    measured_current = np.array([float(row['id_ma']) for row in measured])
    matched_voltage = np.interp(measured_uin, voltage_wave['uin_v'], voltage_wave['value'])
    matched_current = np.interp(measured_uin, sweep, simulated_current)
    delta_voltage = matched_voltage - measured_voltage
    delta_current = matched_current - measured_current
    relative_error = np.divide(delta_current * 100, np.abs(measured_current), out=np.full_like(delta_current, np.nan), where=measured_current != 0)
    comparison_rows = [
        [row['direction'], measured_uin[index], measured_voltage[index], measured_current[index],
         matched_voltage[index], matched_current[index], delta_voltage[index], delta_current[index],
         float(relative_error[index]) if np.isfinite(relative_error[index]) else None]
        for index, row in enumerate(measured)
    ]
    write_csv(data_directory / 'matched_comparison.csv', ['direction', 'uin_v', 'measured_ud_v', 'measured_id_ma', 'simulated_ud_v', 'simulated_id_ma', 'delta_ud_v', 'delta_id_ma', 'relative_id_error_pct'], comparison_rows)
    significant = np.abs(measured_current) >= 0.1
    largest = int(np.argmax(np.where(significant, np.abs(relative_error), -1)))
    metrics = {
        'solver': 'Altium Designer Winter 09 Mixed Sim',
        'source_sdf_sha256': hashlib.sha256(sdf_path.read_bytes()).hexdigest(),
        'model': 'Motorola 1N4735 bundled model',
        'temperature_c': 27,
        'resistance_ohm': 1000,
        'saved_ud_points': len(voltage_wave['uin_v']),
        'saved_current_points': len(sweep),
        'measured_points': len(measured),
        'current_method': 'Saved Altium R1 current, A converted to mA',
        'iv_voltage_method': 'Ud linearly interpolated at the saved R1 current sweep coordinates',
        'maximum_independent_kvl_residual_ma': float(np.max(np.abs(kvl_residual))),
        'mean_absolute_voltage_difference_v': float(np.mean(np.abs(delta_voltage))),
        'mean_absolute_current_difference_ma': float(np.mean(np.abs(delta_current))),
        'measured_current_voltage_relation_max_abs_ma': float(np.max(np.abs(measured_uin - measured_voltage - measured_current))),
        'maximum_relative_current_error_for_measured_abs_ge_0_1ma_pct': float(np.max(np.abs(relative_error[significant]))),
        'largest_relative_error_case': comparison_rows[largest],
        'independent_equation_check': check,
    }
    (data_directory / 'comparison_metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding='utf-8')

    font_path = Path('C:/Windows/Fonts/msyh.ttc')
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams['font.family'] = font_manager.FontProperties(fname=str(font_path)).get_name()
    plt.rcParams['axes.unicode_minus'] = False
    plt.rcParams['font.size'] = 10
    blue, red = '#2864A9', '#C94B40'

    def draw_characteristic(axis, x_limits, y_limits, title):
        axis.plot(simulated_voltage, simulated_current, color=blue, linewidth=1.8, label='Altium 原始电流')
        axis.scatter(measured_voltage, measured_current, s=24, facecolors='white', edgecolors=red, linewidths=1.1, label='实测数据', zorder=3)
        axis.axhline(0, color='#777777', linewidth=0.6)
        axis.grid(True, color='#DCE1E7', linewidth=0.6)
        axis.set(xlim=x_limits, ylim=y_limits, xlabel='二极管电压 Ud / V', ylabel='二极管电流 Id / mA')
        axis.set_title(title, loc='left', fontsize=12)

    figure, axes = plt.subplots(2, 2, figsize=(13.6, 9), layout='constrained')
    draw_characteristic(axes[0, 0], (-6.6, 1.2), (-15, 21), '完整伏安特性')
    axes[0, 0].legend(frameon=False, loc='upper left')
    draw_characteristic(axes[0, 1], (0.5, 0.9), (-0.3, 20.5), '正向导通区')
    draw_characteristic(axes[1, 0], (-6.35, -5.5), (-14.5, 0.5), '反向击穿区')
    for name, mask, color in [('正向', measured_uin >= 0, blue), ('反向', measured_uin < 0, red)]:
        selected = mask & significant
        axes[1, 1].scatter(measured_uin[selected], relative_error[selected], s=25, color=color, label=name)
    axes[1, 1].axhline(0, color='#777777', linewidth=0.7)
    axes[1, 1].grid(True, color='#DCE1E7', linewidth=0.6)
    axes[1, 1].set(xlabel='输入电压 Uin / V', ylabel='ΔId / |Id实测| × 100%')
    axes[1, 1].set_title('同一 Uin 的相对电流误差（|Id实测| ≥ 0.1 mA）', loc='left', fontsize=11)
    axes[1, 1].legend(frameon=False)
    figure.suptitle('1N4735A 仿真与实测核查', fontsize=16)
    figure.savefig(project / 'comparison.png', dpi=200, facecolor='white')
    plt.close(figure)

    figure, axis = plt.subplots(figsize=(10, 5.7), layout='constrained')
    axis.plot(simulated_voltage, simulated_current, color=blue, linewidth=1.8)
    axis.axhline(0, color='#777777', linewidth=0.6)
    axis.grid(True, color='#DCE1E7', linewidth=0.6)
    axis.set(xlabel='二极管电压 Ud / V', ylabel='二极管电流 Id / mA', title='1N4735A 伏安特性 · Altium 原始电流', xlim=(-6.6, 1.2), ylim=(-15, 21))
    figure.savefig(project / 'simulation_curve.png', dpi=220, facecolor='white')
    plt.close(figure)
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
