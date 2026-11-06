"""Import local CSV/JSON recordings for capture replay; files stay Git-ignored."""
import argparse
import shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path,help='Original data/runs folder')
    args=parser.parse_args()
    source=args.source.resolve();target=(ROOT/'data/runs').resolve()
    if source==target:raise SystemExit('Source is already the local recordings folder.')
    count=0
    for path in source.rglob('*'):
        if not path.is_file() or path.suffix not in ('.csv','.json') or '.ipynb_checkpoints' in path.parts:continue
        destination=target/path.relative_to(source)
        if destination.exists():
            if destination.read_bytes()!=path.read_bytes():raise SystemExit('Different existing file: '+str(destination))
            continue
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(path,destination);count+=1
    print(f'Imported {count} local data files to data/runs/. Source files were not changed.')


if __name__=='__main__':main()
