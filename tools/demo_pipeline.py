"""Exercise raw sampling -> features -> candidate rules without hardware."""
import json
import math
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from lab_suite import simulated
from candidate_rules import analyze_synchronous, pressure_rate
from frame5_analysis import motion_score
import numpy as np


def main():
    rows=[]
    for ms in range(0,20001,4):
        rows.append(simulated('ecg',ms/1000,len(rows),bpm=75))
        if ms%40==0:
            rows.append(simulated('imu',ms/1000,len(rows),control=20))
        if ms%100==0:
            for offset in (0,50):
                at=ms+offset
                if at>20000:continue
                r=simulated('pressure',at/1000,len(rows))
                r['pressure_adc']=round(1400+700*max(0,math.sin(2*math.pi*at/2000))**6)
                rows.append(r)
    result=analyze_synchronous(rows,'静坐自然呼吸',True)
    imu=[r for r in rows if r['kind']=='imu']
    A=float(np.std(np.linalg.norm([[r[k] for k in ('ax_g','ay_g','az_g')] for r in imu],axis=1)))
    G=float(np.sqrt(np.mean(np.sum(np.asarray([[r[k] for k in ('gx_dps','gy_dps','gz_dps')] for r in imu])**2,axis=1))))
    parameters=json.loads((ROOT/'models/reference_frame5.json').read_text())['motion_score']
    output={'data_source':'SIMULATED','samples':len(rows),'duration_s':20,
            'live_legacy_profile':result,
            'offline_frame5_motion_score':motion_score(A,G,parameters),
            'hardware_commands_sent':0}
    path=ROOT/'reports/synthetic_demo.json';path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(output,indent=2)+'\n')
    print(json.dumps({'output':'reports/synthetic_demo.json','samples':len(rows),
                      'HR_bpm':result['channels']['ecg']['value'],
                      'pressure_pulses_per_min':result['channels']['pressure']['value'],
                      'legacy_Q':result['channels']['imu']['value'],
                      'frame5_S':output['offline_frame5_motion_score'],'hardware_commands_sent':0},indent=2))


if __name__=='__main__':main()
