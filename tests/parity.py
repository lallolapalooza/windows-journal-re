import sys, os, glob, difflib, subprocess, json
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(ROOT, 'src'))
from jntread.document import Document
from jntread.xmlexport import document_xml

def oracle(path):
    r = subprocess.run([sys.executable, os.path.join(ROOT, 'scripts', 'oracle_direct.py'), path],
                       capture_output=True)
    return r.returncode, r.stdout.decode('utf-8', 'replace')

def check(path):
    rc, ref = oracle(path)
    if rc != 0:
        return path, 'oracle-failed', ref
    got = document_xml(Document.parse(open(path, 'rb').read()))
    if got == ref:
        return path, 'OK', ''
    diff = '\n'.join(difflib.unified_diff([ref], [got], 'oracle', 'ours', n=0))[:2000]
    return path, 'DIFF', diff

if not os.path.exists(os.path.join(ROOT, 'samples', 'Journal.jnt')):
    print('skipped: requires extracted Microsoft samples (see tests/README.md)')
    raise SystemExit(0)
paths = sorted(glob.glob(os.path.join(ROOT, 'samples', '*.jtp'))) + [os.path.join(ROOT, 'samples', 'Journal.jnt')]
paths += sorted(glob.glob(os.path.join(ROOT, 'out', 'corpus_*.jnt')))
ok = 0
for p in paths:
    name, status, diff = check(p)
    print('%-32s %s' % (os.path.basename(name), status))
    if status != 'OK':
        print(diff)
    else:
        ok += 1
print('%d/%d OK' % (ok, len(paths)))
