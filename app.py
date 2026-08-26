import os, sqlite3, secrets
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, redirect, url_for, session, render_template_string, jsonify, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.getenv('NETFI_SECRET_KEY', secrets.token_hex(32))
DB = os.getenv('DATABASE_PATH', 'netfi.db')

def db():
    c = sqlite3.connect(DB); c.row_factory = sqlite3.Row; return c

def init_db():
    c=db(); cur=c.cursor()
    cur.executescript('''
    CREATE TABLE IF NOT EXISTS admins(id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS customers(id INTEGER PRIMARY KEY, name TEXT, phone TEXT UNIQUE, email TEXT, created_at TEXT);
    CREATE TABLE IF NOT EXISTS packages(id INTEGER PRIMARY KEY, name TEXT UNIQUE, price INTEGER, duration_minutes INTEGER, rate_limit TEXT, active INTEGER DEFAULT 1);
    CREATE TABLE IF NOT EXISTS vouchers(id INTEGER PRIMARY KEY, code TEXT UNIQUE, package_id INTEGER, used_by INTEGER, created_at TEXT, used_at TEXT);
    CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, customer_id INTEGER, package_id INTEGER, device_mac TEXT, started_at TEXT, expires_at TEXT, active INTEGER DEFAULT 1);
    ''')
    email=os.getenv('NETFI_ADMIN_EMAIL','admin@netfi.local'); password=os.getenv('NETFI_ADMIN_PASSWORD','ChangeMe123!')
    if not cur.execute('SELECT 1 FROM admins WHERE email=?',(email,)).fetchone():
        cur.execute('INSERT INTO admins(email,password,created_at) VALUES(?,?,?)',(email,generate_password_hash(password),datetime.utcnow().isoformat()))
    c.commit(); c.close()
init_db()

def login_required(f):
 @wraps(f)
 def w(*a,**k):
  if not session.get('admin'): return redirect(url_for('login'))
  return f(*a,**k)
 return w

BASE='''<!doctype html><title>Netfi Billing System</title><style>body{font-family:Arial;max-width:1000px;margin:35px auto;padding:0 18px;background:#f5f7fb}nav a{margin-right:15px}table{width:100%;border-collapse:collapse;background:white}td,th{padding:10px;border-bottom:1px solid #ddd;text-align:left}.card{background:white;padding:20px;border-radius:10px;margin:15px 0}input,select,button{padding:10px;margin:5px}button{cursor:pointer}</style><nav><b>NETFI</b> | <a href='/'>Dashboard</a><a href='/customers'>Customers</a><a href='/packages'>Packages</a><a href='/vouchers'>Vouchers</a><a href='/sessions'>Sessions</a><a href='/logout'>Logout</a></nav>{{body|safe}}'''
def page(body): return render_template_string(BASE,body=body)

@app.route('/login',methods=['GET','POST'])
def login():
 if request.method=='POST':
  row=db().execute('SELECT * FROM admins WHERE email=?',(request.form['email'],)).fetchone()
  if row and check_password_hash(row['password'],request.form['password']): session['admin']=row['email']; return redirect('/')
  return 'Invalid login',401
 return '''<h2>Netfi Billing System</h2><form method=post><input name=email placeholder=Email required><input name=password type=password placeholder=Password required><button>Login</button></form>'''
@app.route('/logout')
def logout(): session.clear(); return redirect('/login')
@app.route('/')
@login_required
def dashboard():
 c=db(); counts={x:c.execute(f'SELECT COUNT(*) n FROM {x}').fetchone()['n'] for x in ['customers','packages','vouchers','sessions']}; active=c.execute('SELECT COUNT(*) n FROM sessions WHERE active=1').fetchone()['n']; c.close()
 return page(f"<h1>Netfi Dashboard</h1><div class=card><b>Customers:</b> {counts['customers']} &nbsp; <b>Packages:</b> {counts['packages']} &nbsp; <b>Vouchers:</b> {counts['vouchers']} &nbsp; <b>Active sessions:</b> {active}</div><div class=card>MikroTik and payment providers can post to the API endpoints after credentials are configured.</div>")
@app.route('/customers',methods=['GET','POST'])
@login_required
def customers():
 c=db()
 if request.method=='POST': c.execute('INSERT INTO customers(name,phone,email,created_at) VALUES(?,?,?,?)',(request.form['name'],request.form['phone'],request.form.get('email',''),datetime.utcnow().isoformat())); c.commit(); return redirect('/customers')
 rows=c.execute('SELECT * FROM customers ORDER BY id DESC').fetchall(); return page("<h2>Customers</h2><form method=post><input name=name placeholder='Full name' required><input name=phone placeholder=Phone required><input name=email placeholder=Email><button>Add customer</button></form>"+table(rows,['id','name','phone','email']))
@app.route('/packages',methods=['GET','POST'])
@login_required
def packages():
 c=db()
 if request.method=='POST': c.execute('INSERT INTO packages(name,price,duration_minutes,rate_limit) VALUES(?,?,?,?)',(request.form['name'],request.form['price'],request.form['duration'],request.form.get('rate_limit',''))); c.commit(); return redirect('/packages')
 rows=c.execute('SELECT * FROM packages ORDER BY id DESC').fetchall(); return page("<h2>Internet Packages</h2><form method=post><input name=name placeholder='Package name' required><input name=price type=number placeholder='Price UGX' required><input name=duration type=number placeholder='Minutes' required><input name=rate_limit placeholder='Rate e.g. 5M/5M'><button>Create package</button></form>"+table(rows,['id','name','price','duration_minutes','rate_limit','active']))
@app.route('/vouchers',methods=['GET','POST'])
@login_required
def vouchers():
 c=db()
 if request.method=='POST':
  code=request.form.get('code') or secrets.token_urlsafe(7).upper(); c.execute('INSERT INTO vouchers(code,package_id,created_at) VALUES(?,?,?)',(code,request.form['package_id'],datetime.utcnow().isoformat())); c.commit(); return redirect('/vouchers')
 packs=c.execute('SELECT id,name FROM packages WHERE active=1').fetchall(); rows=c.execute('SELECT vouchers.*,packages.name package FROM vouchers LEFT JOIN packages ON packages.id=vouchers.package_id ORDER BY vouchers.id DESC').fetchall(); opts=''.join(f"<option value='{p['id']}'>{p['name']}</option>" for p in packs); return page(f"<h2>Vouchers</h2><form method=post><input name=code placeholder='Leave blank to generate'><select name=package_id>{opts}</select><button>Create voucher</button></form>"+table(rows,['id','code','package','used_by','created_at','used_at']))
@app.route('/sessions')
@login_required
def sessions():
 rows=db().execute('SELECT sessions.*,customers.name customer,packages.name package FROM sessions LEFT JOIN customers ON customers.id=sessions.customer_id LEFT JOIN packages ON packages.id=sessions.package_id ORDER BY sessions.id DESC').fetchall(); return page('<h2>Sessions</h2>'+table(rows,['id','customer','package','device_mac','started_at','expires_at','active']))
def table(rows, cols):
 head=''.join(f'<th>{x}</th>' for x in cols); body=''.join('<tr>'+''.join(f'<td>{r[x] if x in r.keys() and r[x] is not None else ""}</td>' for x in cols)+'</tr>' for r in rows); return f'<table><tr>{head}</tr>{body}</table>'
@app.post('/api/v1/vouchers/redeem')
def redeem():
 data=request.get_json(force=True); code=data.get('code','').strip().upper(); customer_id=data.get('customer_id'); mac=data.get('device_mac','')
 c=db(); v=c.execute('SELECT * FROM vouchers WHERE code=? AND used_at IS NULL',(code,)).fetchone()
 if not v: return jsonify(error='invalid or used voucher'),400
 p=c.execute('SELECT * FROM packages WHERE id=?',(v['package_id'],)).fetchone(); now=datetime.utcnow(); exp=now+timedelta(minutes=p['duration_minutes']); c.execute('UPDATE vouchers SET used_by=?,used_at=? WHERE id=?',(customer_id,now.isoformat(),v['id'])); c.execute('INSERT INTO sessions(customer_id,package_id,device_mac,started_at,expires_at) VALUES(?,?,?,?,?)',(customer_id,p['id'],mac,now.isoformat(),exp.isoformat())); c.commit(); return jsonify(ok=True,expires_at=exp.isoformat(),rate_limit=p['rate_limit'])
@app.get('/api/v1/health')
def health(): return jsonify(status='ok',service='netfi-billing-system')
if __name__=='__main__': app.run(host='0.0.0.0',port=int(os.getenv('PORT',8000)),debug=True)
