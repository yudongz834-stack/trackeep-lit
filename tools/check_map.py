"""从 Python 源码生成架构事实；只改有标记的机器块。"""
import argparse
import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / '规则/架构.md'
BEGIN = '<!-- map:modules begin 工具生成·禁止手改 -->'
END = '<!-- map:modules end -->'

def facts():
    rows=[]
    paths=sorted([*ROOT.glob('*.py'), *ROOT.glob('lit/**/*.py'), *ROOT.glob('ui/**/*.py'), *ROOT.glob('tools/*.py')])
    for path in paths:
        source=path.read_text(encoding='utf-8-sig')
        tree=ast.parse(source)
        imports=set()
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom) and node.module and node.module.split('.')[0] in ('lit','ui'):
                imports.add(node.module)
            if isinstance(node,ast.Import):
                imports.update(n.name for n in node.names if n.name.split('.')[0] in ('lit','ui'))
        rows.append({'file':path.relative_to(ROOT).as_posix(), 'lines':len(source.splitlines()),
                     'local_imports':sorted(imports), 'entrypoints':[n.name for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef))]})
    return {'modules':rows,'tests':sorted(p.relative_to(ROOT).as_posix() for p in (ROOT/'tests').glob('*.py'))}

def rendered():
    data=facts()
    rows=['| 源文件 | 行数 | 本仓依赖 |','|---|---:|---|']
    rows.extend(f'| `{r["file"]}` | {r["lines"]} | '+', '.join(r['local_imports'])+' |' for r in data['modules'])
    rows += ['', '测试边界：'+ '、'.join('`'+x+'`' for x in data['tests'])]
    return '\n'.join(rows)

def update(text):
    if text.count(BEGIN)!=1 or text.count(END)!=1 or text.index(BEGIN)>text.index(END):
        raise ValueError('地图机器块缺失、重复或倒置，拒绝写入')
    before,tail=text.split(BEGIN)
    _,after=tail.split(END)
    return before+BEGIN+'\n'+rendered()+'\n'+END+after

def main():
    parser=argparse.ArgumentParser()
    g=parser.add_mutually_exclusive_group(required=True)
    for name in ('write','check','stdout','json'): g.add_argument('--'+name,action='store_true')
    args=parser.parse_args()
    if args.json:
        print(json.dumps(facts(),ensure_ascii=False)); return 0
    try:
        text=MAP.read_text(encoding='utf-8')
        target=update(text)
    except (OSError,ValueError,SyntaxError) as e:
        print(str(e)); return 1
    if args.write: MAP.write_text(target,encoding='utf-8')
    if args.stdout: print(target)
    if args.check and target!=text:
        print('架构事实漂移，先运行 --write 更新'); return 1
    return 0

if __name__=='__main__': sys.exit(main())
