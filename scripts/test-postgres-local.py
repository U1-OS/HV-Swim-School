"""Run the API contract suite against a private, disposable local PostgreSQL server."""
import os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pgserver,pytest
if __name__=='__main__':
    root=ROOT/'data/local-preview/postgres-tests';root.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as folder:
        server=pgserver.get_server(Path(folder),cleanup_mode='stop')
        try:
            os.environ['HV_TEST_POSTGRES_URL']=server.get_uri()
            result=pytest.main(['tests/test_api.py','tests/test_launch_operations.py','tests/test_workforce.py','tests/test_payroll_adapter.py','tests/test_postgres_migration.py','-q','-x',*sys.argv[1:]])
        finally:server.cleanup()
    raise SystemExit(result)
