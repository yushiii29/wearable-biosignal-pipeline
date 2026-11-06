"""Create and push an authenticated user's private repository, then verify it."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def run(args,check=True):
    return subprocess.run(args,cwd=ROOT,text=True,capture_output=True,check=check)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gh',default=shutil.which('gh'))
    parser.add_argument('--name',default='wearable-biosignal-pipeline')
    args=parser.parse_args()
    if not args.gh:raise SystemExit('Install or provide the official GitHub CLI, then sign in first.')
    status=run([args.gh,'auth','status','--hostname','github.com'],check=False)
    if status.returncode:raise SystemExit('GitHub sign-in is required. Run gh auth login --web first.')
    user=json.loads(run([args.gh,'api','user']).stdout)
    login=user['login'];name=f'{login}/{args.name}'
    existing=run([args.gh,'repo','view',name,'--json','nameWithOwner'],check=False)
    if existing.returncode==0:raise SystemExit('Repository already exists; inspect it before pushing: '+name)
    if (ROOT/'.git').exists():
        remotes=run(['git','remote']).stdout.strip()
        if remotes:raise SystemExit('Existing Git remotes found. Inspect them before publishing.')
    else:
        run(['git','init','--initial-branch=main'])
    run(['git','config','user.name',login])
    run(['git','config','user.email',f"{user['id']}+{login}@users.noreply.github.com"])
    run(['git','add','.'])
    pending=run(['git','diff','--cached','--name-only']).stdout.strip()
    if pending:run(['git','commit','-m','Collect Frame 5 biosignal pipeline and reproducible models'])
    created=run([args.gh,'repo','create',args.name,'--private','--source',str(ROOT),
                 '--remote','origin','--push',
                 '--description','Wearable biosignal acquisition, signal processing, reproducible models and Arduino bench control'],check=False)
    if created.returncode:raise SystemExit(created.stderr or created.stdout)
    info=json.loads(run([args.gh,'repo','view',name,'--json','url,isPrivate,nameWithOwner']).stdout)
    if not info['isPrivate']:raise SystemExit('Private visibility verification failed; inspect the repository immediately.')
    result={'uploaded':True,'repository':info['nameWithOwner'],'url':info['url'],'visibility':'PRIVATE'}
    folder=ROOT/'.runtime';folder.mkdir(exist_ok=True)
    (folder/'github_publish.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
