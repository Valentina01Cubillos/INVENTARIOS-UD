"""Provision the downloaded portable PostgreSQL and migrate the local SQLite data.

Run with the project's virtualenv, from Proyecto_Web. No system service is installed.
Credentials are generated locally and never printed.
"""
import os
from pathlib import Path
import secrets
import subprocess
import sys
from datetime import datetime

BASE=Path(__file__).resolve().parents[1]
os.chdir(BASE)
sys.path.insert(0,str(BASE))
RUNTIME=BASE/'.runtime'
BIN=RUNTIME/'pgsql/bin'
DATA=RUNTIME/'pgdata'
FLAGS=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0

def run(arguments, **kwargs):
    if Path(arguments[0]).name=='pg_ctl.exe':
        kwargs.pop('capture_output',None)
        kwargs.update(stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=90)
    return subprocess.run(arguments,check=True,creationflags=FLAGS,**kwargs)

def main():
    from dotenv import dotenv_values,set_key
    import psycopg
    from psycopg import sql
    environment=dotenv_values(BASE/'.env')
    if not (BIN/'initdb.exe').exists():
        raise RuntimeError('Faltan los binarios oficiales de PostgreSQL en .runtime/pgsql.')
    if (DATA/'PG_VERSION').exists() and environment.get('DB_ENGINE')=='postgresql':
        print('Ya existe la base portable. Use manage.py o iniciar.ps1 para iniciarla.'); return
    if environment.get('DB_ENGINE')!='sqlite':
        raise RuntimeError('Esta herramienta migra la instalación local SQLite; no reemplaza otra base PostgreSQL.')
    # Export while still using the old settings. Natural keys preserve permissions and users.
    os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
    import django
    django.setup()
    from django.core.management import call_command
    from django.db import transaction
    backups=BASE/'backups';backups.mkdir(exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    fixture=backups/f'traslado_postgresql_{stamp}.json'
    with fixture.open('w',encoding='utf-8') as stream, transaction.atomic():
        call_command('dumpdata',natural_foreign=True,natural_primary=True,exclude=['contenttypes','auth.permission','admin.logentry','sessions'],stdout=stream)
    app_password=secrets.token_urlsafe(40)
    if not (DATA/'PG_VERSION').exists():
        owner_password=secrets.token_urlsafe(40)
        pwfile=RUNTIME/'bootstrap_password'
        pwfile.write_text(owner_password,encoding='utf-8')
        try:
            run([str(BIN/'initdb.exe'),'-D',str(DATA),'-U','labmanager_owner','--encoding=UTF8','--locale=C','--auth=scram-sha-256','--pwfile='+str(pwfile)],capture_output=True)
        finally:
            pwfile.unlink(missing_ok=True)
        with (DATA/'postgresql.conf').open('a',encoding='utf-8') as stream:
            stream.write("\n# Dedicated LabManager instance\nport = 55432\nlisten_addresses = '127.0.0.1'\n")
        (RUNTIME/'postgres-admin.env').write_text('PGUSER=labmanager_owner\nPGPASSWORD='+owner_password+'\nPGPORT=55432\n',encoding='utf-8')
    else:
        owner_password=dotenv_values(RUNTIME/'postgres-admin.env')['PGPASSWORD']
    status=subprocess.run([str(BIN/'pg_ctl.exe'),'-D',str(DATA),'status'],creationflags=FLAGS,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    if status.returncode: run([str(BIN/'pg_ctl.exe'),'-D',str(DATA),'-l',str(RUNTIME/'postgres.log'),'-w','start'])
    with psycopg.connect(host='127.0.0.1',port=55432,user='labmanager_owner',password=owner_password,dbname='postgres',autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_roles WHERE rolname='labmanager_app'").fetchone():
            conn.execute(sql.SQL('ALTER ROLE labmanager_app PASSWORD {}').format(sql.Literal(app_password)))
        else: conn.execute(sql.SQL('CREATE ROLE labmanager_app LOGIN CREATEDB PASSWORD {}').format(sql.Literal(app_password)))
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname='labmanager'").fetchone(): conn.execute('CREATE DATABASE labmanager OWNER labmanager_app')
    old_env=(BASE/'.env').read_text(encoding='utf-8')
    (backups/f'entorno_antes_postgresql_{stamp}.env').write_text(old_env,encoding='utf-8')
    values={'DB_ENGINE':'postgresql','DB_NAME':'labmanager','DB_USER':'labmanager_app','DB_PASSWORD':app_password,'DB_HOST':'127.0.0.1','DB_PORT':'55432'}
    for k,v in values.items(): set_key(str(BASE/'.env'),k,v)
    child_env=os.environ.copy()
    child_env.update(values)
    try:
        run([sys.executable,'manage.py','migrate','--noinput'],env=child_env)
        run([sys.executable,'manage.py','loaddata',str(fixture)],env=child_env)
        run([sys.executable,'manage.py','crear_roles'],env=child_env)
        run([sys.executable,'manage.py','check'],env=child_env)
    except Exception:
        (BASE/'.env').write_text(old_env,encoding='utf-8')
        raise RuntimeError('El traslado no terminó; .env vuelve a SQLite. El respaldo y PostgreSQL se conservan para recuperación.')
    print('PostgreSQL listo en 127.0.0.1:55432. Datos y usuarios trasladados; SQLite conservado.')

if __name__=='__main__': main()
