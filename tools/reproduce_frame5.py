"""Rebuild all three Frame 5 models from the included capture-level features."""
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from frame5_analysis import reproduce_frame5


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'reports/frame5_reproduced.json')
    args=parser.parse_args()
    result=reproduce_frame5()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    models=ROOT/'models/frame5_models.json'
    models.write_text(json.dumps({k:result[k] for k in ('profile','pressure_cutoff','motion_score','pressure','imu','ecg')},indent=2)+'\n')
    print(json.dumps({'output':str(args.output.relative_to(ROOT)) if args.output.is_relative_to(ROOT) else str(args.output),
                      'counts':result['counts'],'pressure_cutoff':result['pressure_cutoff'],
                      'motion_cutoff':result['motion_score']['candidate_boundary'],
                      'ecg_fitted_zero':result['ecg']['fitted_zero'],
                      'ecg_project_reference':100.0,'hardware_commands_sent':0},indent=2))


if __name__=='__main__':
    main()
