"""Extract original per-recording features from local manually reviewed CSVs."""
import argparse
import csv
import json
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from candidate_rules import pressure_rate
from ecg_analysis import analyze_ecg


def extract(path):
    meta=json.loads(path.with_suffix('.json').read_text())
    kind=meta['kind']
    with path.open(encoding='utf-8-sig',newline='') as stream:
        fields={'t_ms','pressure_adc','ecg_adc','ax_g','ay_g','az_g','gx_dps','gy_dps','gz_dps'}
        rows=[{k:float(v) for k,v in r.items() if k in fields and v!=''} for r in csv.DictReader(stream)]
    features={}
    if not rows:return {'kind':kind,'features':{},'status':'no_samples'}
    if kind=='pressure':
        features['pressure_rate'],_=pressure_rate(rows)
    elif kind=='imu':
        a=np.asarray([[r[k] for k in ('ax_g','ay_g','az_g')] for r in rows])
        g=np.asarray([[r[k] for k in ('gx_dps','gy_dps','gz_dps')] for r in rows])
        features={'accel_sd':float(np.std(np.linalg.norm(a,axis=1))),
                  'gyro_rms':float(np.sqrt(np.mean(np.sum(g*g,axis=1))))}
    elif kind=='ecg':
        features['heart_rate']=analyze_ecg(rows,meta.get('ecg_polarity',1))['bpm']
    else:
        return {'kind':kind,'features':{},'status':'not_a_single_sensor_training_capture'}
    return {'capture_id':meta.get('capture_id'),'kind':kind,'features':features,'status':'extracted'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs',type=Path,default=ROOT/'data/runs/可用于比较')
    parser.add_argument('--output',type=Path,default=ROOT/'local_private/extracted_features.json')
    args=parser.parse_args();results=[]
    for path in sorted(args.runs.glob('*.csv')):
        meta=json.loads(path.with_suffix('.json').read_text())
        if meta.get('review_status')=='keep' and meta.get('source')=='DEVICE':results.append(extract(path))
    if not results:raise SystemExit('No reviewed real-device captures found. Import the local dataset first.')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'records':results},indent=2)+'\n')
    print(f'Extracted {len(results)} recordings into {args.output.name}; raw recordings unchanged.')


if __name__=='__main__':main()
