"""Start this project's private cluster after a reboot; never touch another server."""
import os
from pathlib import Path
import subprocess

def ensure_started():
    base=Path(__file__).resolve().parent.parent
    cluster=base/'.runtime/pgdata'
    executable=base/'.runtime/pgsql/bin/pg_ctl.exe'
    if not executable.exists() or not (cluster/'PG_VERSION').exists(): return
    if os.getenv('DB_ENGINE')!='postgresql' or os.getenv('DB_PORT')!='55432' or os.getenv('DB_HOST')!='127.0.0.1': return
    kwargs={'creationflags':subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0,'capture_output':True,'timeout':60}
    status=subprocess.run([str(executable),'-D',str(cluster),'status'],**kwargs)
    if status.returncode:
        result=subprocess.run([str(executable),'-D',str(cluster),'-l',str(base/'.runtime/postgres.log'),'-w','start'],creationflags=kwargs['creationflags'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=60)
        if result.returncode: raise RuntimeError('No se pudo iniciar PostgreSQL local. Revise .runtime/postgres.log.')
