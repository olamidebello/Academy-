# Academy
Multi-tenant school operations for preschool through university at academy.africandroid.world.

## Run
Python 3.11+; core has no external dependencies.
```
python3 manage.py init
python3 manage.py create-superadmin dobcalldemo@gmail.com
python3 app.py
```
Open http://127.0.0.1:18840. Passwords are entered privately, never shipped as defaults.

## Deploy on Debian
```
ansible-pull -U https://github.com/olamidebello/Academy-.git -C main -d /opt/academy-deploy-source -i localhost, -c local ansible/deploy.yml
sudo -u academy env ACADEMY_DB=/var/lib/academy/academy.db python3 /opt/academy/manage.py create-superadmin dobcalldemo@gmail.com
```
Point academy.africandroid.world DNS at the server. Configure HTTPS using your hosting panel or certbot before signing in: secure session cookies require HTTPS. The playbook creates the HTTP origin only and must not replace an existing HTTPS vhost without review. Back up /var/lib/academy/academy.db with SQLite backup API. Gunicorn is used in deployment; development server is local only.

## Included implementation
Tenant-scoped institution records; password hashing and role checks; admissions, students, courses, programs, lessons, assignment submissions, attendance, weighted grading and printable reports, progress observations, staff records, salary and promotion history, campus services records, invoices, announcements, online choice/essay exam delivery with server deadlines and saved answers, geofence time clock, completed-shift payroll drafts, audit log, user provisioning and institution creation.

## Current limits and rollout requirements
This is an initial working release, not completion of every requested module. Modules for campus services are record registers. Promotions are history records and do not automatically update salary. Superadmins can create and switch institution workspaces, then provision institution administrators; no public tenant signup. Parent-child linking, published student report access, essay marking workflow, report approval, full GPA/transcripts, live classroom integration, files, payment gateways, real payroll payments/tax engines, forgot-password email, MFA, mobile app, proctoring, backups scheduling and full staff HR workflows remain to be implemented. Payroll salaries apply to the selected period without proration; only complete in/out pairs count for hourly payroll. Location accuracy is checked at punch time but does not prove physical presence. Institution administrators must review all payroll drafts before external payment.

Run `python3 -m unittest discover -s tests -v`. Live deployment requires DNS, HTTPS, backups and acceptance/security review before sensitive student or payroll data is entered.

## Rebuild and repair wrong-site routing
If Academy shows SprintForge or another default site, run as root:
```bash
ansible-pull -U https://github.com/olamidebello/Academy-.git -C main -d /opt/academy-hard-repair-source -i localhost, -c local ansible/hard-repair.yml -e academy_email=dobcalldemo@gmail.com
```
This uses a new dated release and isolated runtime; runs tests; backs up SQLite; initializes additive tables; restores Academy service permissions; repairs exact Academy server_name conflicts without stopping SprintForge or deleting its records; validates nginx; reuses or obtains a trusted certificate; and verifies Academy identity over local HTTPS. Existing working nginx configuration is required. If nginx is already syntactically invalid, the playbook stops and reports the error rather than editing unrelated sites.

Only Academy's exact server_name is removed from conflicting blocks. Wildcard/default hosts and other names are preserved. A certificate request requires correct public DNS and reachable port 80; CDN/origin problems must be corrected separately. Certificate issuance is subject to CA limits. Location of routing backup and report: `/var/lib/academy-repair/latest-report.json`. Code/database-before backup: `/opt/academy-releases/<timestamp>/`. Never run the older deploy playbook after this repair, as it can reintroduce a duplicate HTTP vhost.

On routing validation failure the helper restores its modified files; on activation failure Ansible restores the previous Academy unit where present. New certificate artifacts and installed packages are retained. Schema initialization creates missing tables only; no user data is deleted or restored automatically. This repairs deployment and routing, not unfinished product features. It has local tests but must be validated on the target server. After success, use the exact create-superadmin command printed by the playbook if no Academy account exists; SprintForge accounts are not automatically migrated.
