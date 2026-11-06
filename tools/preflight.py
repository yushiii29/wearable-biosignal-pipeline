"""Check publication contents without contacting GitHub."""
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]


def main():
    result=subprocess.run(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT,
                          text=True,capture_output=True,check=True)
    names=[name for name in result.stdout.split('\0') if name]
    problems=[]
    forbidden=('data/runs/','local_private/','.runtime/','.jupyter/','.venv/','__pycache__/')
    for name in names:
        path=ROOT/name
        if any(name.startswith(p) for p in forbidden) or name.endswith('.pyc'):
            problems.append('Private/generated file: '+name)
        if path.stat().st_size>90*1024*1024:problems.append('Oversized file: '+name)
        if path.suffix=='.png':continue
        text=path.read_text(encoding='utf-8',errors='replace')
        if '/Users/' in text and path.name!='preflight.py':problems.append('Absolute home path: '+name)
        if re.search(r'(?:github_pat_|ghp_)[A-Za-z0-9_]{20,}',text):problems.append('Possible GitHub credential: '+name)
        if re.search(r'token=[a-zA-Z0-9_-]{30,}',text):problems.append('Possible login token: '+name)
        if path.suffix=='.ipynb':
            notebook=json.loads(text)
            if notebook.get('metadata',{}).get('widgets'):problems.append('Saved widget state: '+name)
            if any(c.get('outputs') for c in notebook['cells']):problems.append('Saved notebook output: '+name)
        if path.suffix=='.md':
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)',text):
                if target.startswith(('https://','http://','#')):continue
                dest=path.parent/unquote(target.split('#')[0])
                if not dest.exists():problems.append('Missing document link: '+name+' -> '+target)
    report={'publication_files':len(names),'total_bytes':sum((ROOT/n).stat().st_size for n in names),
            'problems':problems,'passed':not problems,
            'intended_visibility':'PRIVATE','github_upload_completed':False}
    destination=ROOT/'reports/publication_preflight.json'
    destination.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if problems:raise SystemExit(1)


if __name__=='__main__':main()
