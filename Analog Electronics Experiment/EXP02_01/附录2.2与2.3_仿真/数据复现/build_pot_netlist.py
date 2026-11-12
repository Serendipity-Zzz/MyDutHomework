from pathlib import Path
import numpy as np
import json

root=Path(__file__).resolve().parents[2]
out=root/'附录2.2与2.3_仿真/Altium'
# Parallel independent copies of the classroom potentiometer circuit permit
# a single native Operating Point run to evaluate every recorded setting.
p=np.unique(np.concatenate([np.linspace(.001,.999,51),np.linspace(.63,.70,36),np.linspace(.47,.53,31)]))
lines=['Potentiometer independent operating-point samples','V1 U1 0 DC 20','V2 U2 0 DC -20']
for i,a in enumerate(p):
    lines += [f'RWA{i} U1 UIN{i} {20000*a:.12g}',f'RWB{i} UIN{i} U2 {20000*(1-a):.12g}',f'R{i} UIN{i} UD{i} 1000',f'D{i} UD{i} 0 1N4735',f'.SAVE UIN{i} UD{i} @R{i}[i]']
lines+=['.OP','.OPTIONS RELTOL=1e-6 ABSTOL=1e-12 VNTOL=1e-9 TEMP=27',(out/'1N4735.mdl').read_text(encoding='ascii'),'.END']
(out/'Pot_OperatingPoints.nsx').write_text('\n'.join(lines),encoding='ascii')
(out.parent/'数据复现/pot_settings.json').write_text(json.dumps(p.tolist()),encoding='ascii')
print('pot settings',len(p))

