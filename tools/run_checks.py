"""Run software-only tests and save a compact verification report."""
import json
import os
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('MPLBACKEND','Agg')


def main():
    folder=ROOT/'reports';folder.mkdir(exist_ok=True)
    suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
    with (folder/'tests.log').open('w') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    report={'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'skipped':len(result.skipped),'successful':result.wasSuccessful(),
            'skipped_reasons':[reason for test,reason in result.skipped],
            'validation_scope':'Software, synthetic signals, virtual serial/HTTP and saved coefficient regression; no hardware commands.'}
    (folder/'test_results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not result.wasSuccessful():
        for test,traceback in result.errors+result.failures:print(str(test)+'\n'+traceback)
        raise SystemExit(1)


if __name__=='__main__':main()
