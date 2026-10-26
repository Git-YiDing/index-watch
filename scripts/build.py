"""Create a dependency-free single HTML file and the deployable static site."""
from pathlib import Path
import json
import argparse
import shutil
ROOT=Path(__file__).resolve().parents[1]

def build(output: Path|None=None):
    site=ROOT/'site'
    data={k:json.loads((site/'data'/filename).read_text(encoding='utf-8')) for k,filename in [('dataset','funds.json'),('health','health.json'),('history','history.json')]}
    returns_path=site/'data/returns.json'
    data['returns']=json.loads(returns_path.read_text(encoding='utf-8')) if returns_path.exists() else {'funds':{}}
    text=(site/'template.html').read_text(encoding='utf-8')
    text=text.replace('/*__CSS__*/',(site/'assets/style.css').read_text(encoding='utf-8'))
    text=text.replace('/*__JS__*/',(site/'assets/app.js').read_text(encoding='utf-8'))
    # Prevent an untrusted data string from closing an inline JSON script element.
    payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    text=text.replace('/*__DATA__*/',payload)
    (site/'index.html').write_text(text,encoding='utf-8')
    (site/'.nojekyll').touch()
    hosting=ROOT/'.openai/hosting.json'
    if hosting.exists() and json.loads(hosting.read_text()).get('static',{}).get('directory')=='dist':
        dist=ROOT/'dist'
        dist.mkdir(exist_ok=True)
        shutil.copy2(site/'index.html',dist/'index.html')
        for directory in ('assets','data'):
            shutil.copytree(site/directory,dist/directory,dirs_exist_ok=True)
    if output:
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(text,encoding='utf-8')
    print(f'Built {len(data["dataset"]["funds"])} rows into {len(text.encode()):,} bytes.')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--standalone',type=Path);a=p.parse_args();build(a.standalone)
