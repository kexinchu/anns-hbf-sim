"""Fetch immutable upstream revisions. No modifications to upstream source."""
import pathlib, subprocess, json, argparse
p=argparse.ArgumentParser();p.add_argument("--all",action="store_true",help="also fetch audit-only repositories");args=p.parse_args()
root=pathlib.Path(__file__).resolve().parent
pins=json.loads((root/'pins.json').read_text())
for name,record in pins.items():
    if not args.all and name not in ("EventLab","HBXim"): continue
    dst=root/'vendor'/name
    if not dst.exists():
        dst.mkdir(parents=True)
        subprocess.run(['git','init',str(dst)],check=True)
        subprocess.run(['git','-C',str(dst),'fetch','--depth','1',record['url'],record['commit']],check=True)
        subprocess.run(['git','-C',str(dst),'checkout','--detach','FETCH_HEAD'],check=True)
    sha=subprocess.check_output(['git','-C',str(dst),'rev-parse','HEAD'],text=True).strip()
    if sha!=record['commit']: raise RuntimeError(f'{name}: revision mismatch')
    if subprocess.check_output(['git','-C',str(dst),'status','--porcelain'],text=True).strip(): raise RuntimeError(f'{name}: upstream dirty')
    print(name,sha)
