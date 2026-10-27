#!/usr/bin/env python3
"""Repair only exact Academy server_name entries; preserve other domains."""
import argparse, datetime, hashlib, json, os, pathlib, re, shutil, sqlite3, subprocess, sys
DOMAIN='academy.africandroid.world'
TOKEN=re.compile(r'#\s*[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{};]|[^\s{};#]+')
def rename_conflicts(text,domain):
    tokens=[m for m in TOKEN.finditer(text) if not m.group().startswith('#')]
    edits=[]; i=0
    while i<len(tokens):
        if tokens[i].group()=='server_name':
            j=i+1
            while j<len(tokens) and tokens[j].group()!=';': j+=1
            if j==len(tokens): raise ValueError('Unterminated server_name directive')
            names=tokens[i+1:j]
            matches=[m for m in names if m.group().strip('\"\'')==domain]
            if matches:
                remaining=[m for m in names if m not in matches]
                replacement='' if remaining else 'academy-disabled-'+hashlib.sha256(text.encode()).hexdigest()[:12]+'.invalid'
                for n,m in enumerate(matches): edits.append((m.start(),m.end(),replacement if n==0 else ''))
            i=j
        i+=1
    for start,end,value in reversed(edits): text=text[:start]+value+text[end:]
    return text,len(edits)
def run(args):
    r=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
    if r.returncode: raise RuntimeError('Command failed: '+args[0]+'\n'+r.stderr[-4000:])
    return r.stdout+r.stderr
def certificate_usable(cert,key,domain):
    if not cert.exists() or not key.exists(): return False
    checks=[['openssl','x509','-checkend','604800','-noout','-in',str(cert)],
            ['openssl','x509','-checkhost',domain,'-noout','-in',str(cert)],
            ['openssl','verify','-purpose','sslserver','-verify_hostname',domain,
             '-CAfile','/etc/ssl/certs/ca-certificates.crt','-untrusted',str(cert),str(cert)]]
    for cmd in checks:
        if subprocess.run(cmd,capture_output=True,timeout=15).returncode: return False
    public=subprocess.run(['openssl','x509','-pubkey','-noout','-in',str(cert)],capture_output=True,timeout=15)
    private=subprocess.run(['openssl','pkey','-pubout','-in',str(key)],capture_output=True,timeout=15)
    return public.returncode==0 and private.returncode==0 and public.stdout==private.stdout
def atomic_write(path,text):
    path=pathlib.Path(path); tmp=path.with_name(path.name+'.academy-tmp'); tmp.write_text(text); os.chmod(tmp,0o644); os.replace(tmp,path)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--domain',default=DOMAIN); p.add_argument('--port',type=int,default=18840); p.add_argument('--email',default=''); p.add_argument('--backup-root',default='/var/lib/academy-repair'); a=p.parse_args()
    if a.domain!=DOMAIN: p.error('This repair is restricted to '+DOMAIN)
    stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); backup=pathlib.Path(a.backup_root)/stamp; backup.mkdir(parents=True,mode=0o700)
    report={'domain':a.domain,'backup':str(backup),'status':'started'}; changes={}; created=[]
    def save_report():
        (backup/'report.json').write_text(json.dumps(report,indent=2)); pathlib.Path(a.backup_root,'latest-report.json').write_text(json.dumps(report,indent=2))
    def remember(path):
        key=str(path)
        if key in changes: return
        if path.exists():
            changes[key]=path.read_text(); dest=backup/'nginx'/key.lstrip('/'); dest.parent.mkdir(parents=True,exist_ok=True); dest.write_text(changes[key])
        else: created.append(path)
    try:
        dump=run(['nginx','-T']); (backup/'nginx-before.txt').write_text(dump)
        db=pathlib.Path('/var/lib/academy/academy.db')
        if db.exists():
            with sqlite3.connect(db) as src, sqlite3.connect(backup/'academy.db') as dst: src.backup(dst)
        files={pathlib.Path(x).resolve() for x in re.findall(r'^# configuration file (.+):$',dump,re.M)}
        target=pathlib.Path('/etc/nginx/conf.d/academy-repaired.conf'); remember(target)
        count=0
        for file in sorted(files):
            if file==target.resolve() or not file.is_file(): continue
            original=file.read_text(); updated,n=rename_conflicts(original,a.domain)
            if n: remember(file); atomic_write(file,updated); count+=n
        root=pathlib.Path('/var/www/academy-acme'); root.mkdir(parents=True,exist_ok=True)
        def config(cert=None,key=None):
            proxy=f'location / {{ proxy_pass http://127.0.0.1:{a.port}; proxy_set_header Host $host; proxy_set_header X-Forwarded-Proto $scheme; proxy_set_header X-Real-IP $remote_addr; }}'
            acme=f'location ^~ /.well-known/acme-challenge/ {{ root {root}; }}'
            if cert:
                return f'''server {{ listen 80; listen [::]:80; server_name {a.domain}; {acme} location / {{ return 301 https://$host$request_uri; }} }}
server {{ listen 443 ssl; listen [::]:443 ssl; server_name {a.domain}; ssl_certificate {cert}; ssl_certificate_key {key}; ssl_protocols TLSv1.2 TLSv1.3; client_max_body_size 1m; {proxy} }}\n'''
            return f'server {{ listen 80; listen [::]:80; server_name {a.domain}; {acme} client_max_body_size 1m; {proxy} }}\n'
        atomic_write(target,config()); run(['nginx','-t']); run(['systemctl','reload','nginx'])
        page=run(['curl','--fail','--silent','--show-error','--max-time','30','--noproxy','*','--resolve',f'{a.domain}:80:127.0.0.1',f'http://{a.domain}/'])
        if '<title>Academy' not in page or 'SprintForge' in page: raise RuntimeError('Local HTTP domain returned the wrong application')
        certdir=pathlib.Path('/etc/letsencrypt/live')/a.domain; cert=certdir/'fullchain.pem'; key=certdir/'privkey.pem'
        usable=certificate_usable(cert,key,a.domain)
        if not usable:
            if not a.email: raise RuntimeError('No trusted, matching Academy TLS certificate. Re-run with -e academy_email=YOUR_EMAIL and ensure public A/AAAA records reach this server.')
            command=['certbot','certonly','--webroot','-w',str(root),'--cert-name',a.domain,'-d',a.domain,'--email',a.email,'--agree-tos','--non-interactive']
            if cert.exists(): command.append('--force-renewal')
            run(command)
        if not certificate_usable(cert,key,a.domain): raise RuntimeError('Certificate failed hostname, expiry, public trust chain or private-key verification')
        atomic_write(target,config(cert,key)); run(['nginx','-t']); run(['systemctl','reload','nginx'])
        page=run(['curl','--fail','--silent','--show-error','--max-time','30','--noproxy','*','--resolve',f'{a.domain}:443:127.0.0.1',f'https://{a.domain}/'])
        if '<title>Academy' not in page or 'SprintForge' in page: raise RuntimeError('HTTPS domain still returns another application')
        health=run(['curl','--fail','--silent','--show-error','--max-time','30','--noproxy','*','--resolve',f'{a.domain}:443:127.0.0.1',f'https://{a.domain}/health'])
        if json.loads(health).get('status')!='ok': raise RuntimeError('HTTPS health verification failed')
        report.update(status='success',conflicting_names_repaired=count,local_https_verified=True,public_dns_verified=False)
    except Exception as e:
        errors=[]
        for path,text in changes.items():
            try: atomic_write(path,text)
            except Exception as restore_error: errors.append(str(restore_error))
        for path in created:
            try: path.unlink(missing_ok=True)
            except Exception as restore_error: errors.append(str(restore_error))
        try: run(['nginx','-t']); run(['systemctl','reload','nginx'])
        except Exception as restore_error: errors.append(str(restore_error))
        report.update(status='failed',reason=str(e),rolled_back=not errors,rollback_errors=errors); save_report(); print(json.dumps(report)); return 1
    save_report(); print(json.dumps(report)); return 0
if __name__=='__main__': sys.exit(main())
