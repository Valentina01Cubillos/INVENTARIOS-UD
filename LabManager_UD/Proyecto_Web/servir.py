"""Run the local WSGI server; portable database starts automatically."""
import argparse
import os
from pathlib import Path
from dotenv import load_dotenv

BASE=Path(__file__).resolve().parent
load_dotenv(BASE/'.env')
from config.portable_db import ensure_started
ensure_started()
from config.wsgi import application
from waitress import serve

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',default=8000,type=int)
    options=parser.parse_args()
    runtime=BASE/'.runtime';runtime.mkdir(exist_ok=True)
    pid_file=runtime/'web.pid'
    pid_file.write_text(str(os.getpid()),encoding='ascii')
    try:
        serve(application,host=options.host,port=options.port,threads=8)
    finally:
        if pid_file.exists() and pid_file.read_text().strip()==str(os.getpid()): pid_file.unlink()
