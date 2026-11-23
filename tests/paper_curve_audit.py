"""Independent output checker plus corrupt-trace negative tests; no EventLab imports."""
import copy,json,pathlib,sys

def check(records, size, qd, hot, dependent):
    requests, s = records[:-1], records[-1]
    assert len(requests) == 1024 and s['requests'] == 1024
    assert {r['id'] for r in requests} == set(range(10000,11024))
    assert s['useful_bytes'] == 1024 * size
    assert s['senses'] == (0 if hot else 1024)
    ordered = sorted(requests, key=lambda r:r['id'])
    outstanding_limit = 1 if dependent else qd
    # Every new parent beyond the initial window must follow a completion.
    completions = sorted(r['complete_ps'] for r in requests)
    for i,r in enumerate(ordered):
        assert r['complete_ps'] > r['submit_ps'] >= 0
        if i < outstanding_limit: assert r['submit_ps'] == 0
        else: assert r['submit_ps'] >= completions[i-outstanding_limit]
        if dependent and i: assert r['submit_ps'] >= ordered[i-1]['complete_ps']
    assert s['elapsed_ps'] == max(completions)
    assert s['peak'] == outstanding_limit
    assert s['elapsed_ps'] >= s['useful_bytes']*1000/1504
    if not hot: assert s['elapsed_ps'] >= 2720000*(1024 if dependent else 1)

def audit(directory):
    points=0;negatives=0
    for path in sorted(pathlib.Path(directory).glob('*-q*.jsonl')):
        size,cache,access,dep,q = path.stem.split('-')
        args=(int(size),int(q[1:]),cache=='hot',dep=='chain')
        records=[json.loads(x) for x in path.read_text().splitlines()]
        check(records,*args);points+=1
        mutants=[]
        r=copy.deepcopy(records);r[-1]['elapsed_ps']+=1;mutants.append(r)
        r=copy.deepcopy(records);r[1]['id']=r[0]['id'];mutants.append(r)
        r=copy.deepcopy(records);r[-1]['senses']+=1;mutants.append(r)
        r=copy.deepcopy(records);r[0]['complete_ps']=-1;mutants.append(r)
        for mutant in mutants:
            try:check(mutant,*args)
            except AssertionError: negatives+=1
            else:raise AssertionError('checker accepted corrupt evidence')
    invalid=len(list(pathlib.Path(directory).glob('*.invalid.json')))
    assert points+invalid==64,(points,invalid)
    result={'points':points,'invalid_points':invalid,'corrupt_outputs_rejected':negatives,'scope':'output and arrival contract; not independent physical timing model'}
    pathlib.Path(directory,'independent-audit.json').write_text(json.dumps(result,indent=2))
    print(result)
if __name__=='__main__':audit(sys.argv[1])
