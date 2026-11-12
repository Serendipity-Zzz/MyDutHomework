from pathlib import Path
import csv
import json
import struct
import hashlib

root=Path(__file__).resolve().parents[2]
folder=root/'附录2.2与2.3_仿真'
source=folder/'Altium/Pot_OperatingPoints.sdf'
data=source.read_bytes()
position=0
waves={}
while position<len(data):
    end=data.find(b'\n',position)
    if end<0:break
    line=data[position:end].decode('ascii',errors='replace').strip()
    position=end+1
    if not line.startswith('Wave:'):continue
    name=line.split(':',1)[1].strip().lower()
    header={}
    while True:
        end=data.find(b'\n',position)
        line=data[position:end].decode('ascii',errors='replace').strip()
        position=end+1
        if line=='WaveDataStart':break
        if ':' in line:
            key,val=line.split(':',1);header[key]=val.strip()
    assert header['WavePoints']=='1'
    x,y=struct.unpack_from('<ff',data,position)
    waves[name]=y
    position+=8

settings=json.loads((folder/'数据复现/pot_settings.json').read_text())
rows=[]
for i,p in enumerate(settings):
    uin=waves[f'uin{i}'];ud=waves[f'ud{i}'];current=waves[f'r{i}[i]']*1000
    rows.append([i+1,p,uin,ud,current,(uin-ud)-current])
with (folder/'数据复现/pot_operating_points.csv').open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.writer(f);writer.writerow(['index','position','uin_v','ud_v','id_ma','kvl_residual_ma']);writer.writerows(rows)
assert len(rows)==118
assert max(abs(r[-1]) for r in rows)<.00001
result={'count':len(rows),'source_sha256':hashlib.sha256(data).hexdigest(),'maximum_kvl_residual_ma':max(abs(r[-1]) for r in rows),'source':'Altium Designer Winter 09 native Operating Point analysis','rows':rows}
(folder/'数据复现/pot_provenance.json').write_text(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='rows'},ensure_ascii=False))
print('representative',rows[0],rows[-1],min(rows,key=lambda r:abs(r[1]-.5)))

