#! /usr/bin/python3

import requests
import subprocess
import getpass

from os import path
from itertools import chain
from zipfile import ZipFile
from sys import argv

CATS_URL = 'http://imcs.dvfu.ru/cats'
INIT_CMD = 'cats init'
PUSHALL_CMD = 'cats pushall'
REMOTE_BRANCH = 'cats-remote'
RC_FILE = '.catsrc'

def _git(args, soft):
	if isinstance(args, str):
		args = args.split()

	try:
		output = subprocess.check_output(chain(('git',), args))

	except subprocess.CalledProcessError as e:
		if soft:
			return e.output, e.returncode
		else:
			print("IM HARD")
			print('git: ', e.output.decode('utf-8'))
			print('args: ', args)
			exit(e.returncode)

	except FileNotFoundError as e:
		print('git: ', e.strerror)
		exit(e.errno)

	else:
		if soft:
			return output, 0
		else:
			return output


git_soft = lambda args: _git(args, soft=True)
git_hard = lambda args: _git(args, soft=False) 


def get(rel_url, **params):
	params['json'] = '1'
	paramstr = ';'.join('='.join(i) for i in params.items())
	return requests.get('{}/{}?{}'.format(CATS_URL, rel_url, paramstr))

def post(rel_url, files=None, **data):
	return requests.post(CATS_URL + '/' + rel_url, files={k: open(v, 'rb') for k, v in files.items()}, data=data)


def download_zip(sid, cid, download):
	r = get('main.pl', f='problems', sid=sid, cid=cid, download=download)
	zip_file_name = r.url.split('/')[-1]
	with open(zip_file_name, 'wb') as f:
		f.write(r.content)
	return zip_file_name


def init(sid=None, cip=None, download=None, taskfile=None, **etc):
	taskfile = taskfile or 'problem.xml'
	if path.exists(taskfile):
		print("Cannot init: file {} exists.".format(taskfile))
		return
	git_hard('init')
	open(taskfile, 'w').write('''<?xml version="1.0" encoding="UTF-8" ?>
<CATS version="1.8">
<Problem title="" lang="ru"
  tlimit="1" mlimit="256" inputFile="input.txt" outputFile="output.txt"
  author="">

<ProblemStatement>
<p>
</p>
</ProblemStatement>

<ProblemConstraints>
<p></p>
</ProblemConstraints>
<InputFormat>
<p>
</p>
</InputFormat>

<OutputFormat>
<p>
</p>
</OutputFormat>

<Sample rank="1"><SampleIn src="01.in"/><SampleOut src="01.out"/></Sample>

<Import guid="std.testlib.h.last" />
<Checker src="check.cpp" name="chk" de_code="102" style="testlib" export="" />
<Solution name="sol" src="" />
<Generator name="gen" src="" />

</Problem>
</CATS>''')

	open('.gitignore', 'w').writelines([
		'.gitignore', '*.zip', RC_FILE, 
		'*.exe', 'a.out', '*.jar', '*.class', 
		'*.stackdump', 'input.txt', 'output.txt'])

	if sid and cid and cpid:
		zip_file_name = download_zip(sid, cid, download)
		with ZipFile(zip_file_name, 'r') as zf:
			zf.extractall()
			git_hard(['add'] + zf.namelist())
			git_hard('commit -m "initial commit"')


def login():
	print('Username: ', end='')
	usr = input()
	pwd = getpass.getpass()
	j = get('main.pl', f='login', login=usr, passwd=pwd).json()
	if 'error' in j:
		print('error:', j['error'])
	return j.get('sid')

def uri_params(uri):
	return dict(p.split('=') for p in uri.split('?')[-1].split(';'))

def prepare_zip():
	git_hard('archive -o problem.zip @')

def extract_console(r):
	ta_s = '<textarea cols="100" rows="10" readonly="readonly">'
	ta_e = '</textarea>'
	r = r[r.find(ta_s) + len(ta_s):]
	r = r[:r.find(ta_e)]
	return r


def update_repo(sid, cid, cpid, download):
	zip_file_name = download_zip(sid, cid, download)

	git_status = git_hard('status --untracked -s'.split())

	if git_status:
		print("There are untracked files in work dir:")
		print(git_status.decode('utf-8'))
		print("They may be unrecoverably overwriten by update.\nDo You want to continue? [y]n:")
		if input() not in 'yY':
			print('You may commit or stash files with git first, and then rerun command, or run `{}`'.format(PUSHALL_CMD))
			return

	ck_cmd = ['checkout']
	if subprocess.call('git rev-parse --verify ' + REMOTE_BRANCH):
		ck_cmd.append('--orphan')
	ck_cmd.append(REMOTE_BRANCH)

	git_hard(ck_cmd)

	with ZipFile(zip_file_name, 'r') as zf:
		zf.extractall()
		git_hard(['add'] + zf.namelist())

	git_soft(['commit', '-m', 'Update remote version'])

	git_hard('merge master')
	git_hard('checkout master')

	prepare_zip()

	r=post('main.pl',
		f='problems',
		files={'zip': 'problem.zip'},
		replace="1",
		sid=sid,
		cid=cid,
		problem_id=cpid).text
	
	print(extract_console(r))

def add_new_task(sid, cid):
	prepare_zip()

	r=post('main.pl',
		f='problems',
		files={'zip': 'problem.zip'},
		add_new="1",
		sid=sid,
		cid=cid)

	print('add http status: ', 'ok' if r.ok else r.status_code)
	
	output = extract_console(r.text)
	print(output)

	S = 'Initialized empty Git repository in /srv/cats/cgi-bin/repos/'
	output = output[output.find(S) + len(S):]
	repo = output[:output.find('/.git/')]

	global data
	data['download'] = repo


def gather_data(sid=None, cid=None, cpid=None, download=None, **etc):
	if not sid or not cid:
		return {}
	if not cpid and not download:
		return {}

	j = get('main.pl', f='problems', sid=sid, cid=cid).json()
	for p in j['problems']:
		dl = uri_params(p['package_url'])['download']
		if p['id'] == cpid or dl == download:
			return dict(cpid=str(p['id']), download=dl)

	return {}


def show_help():
	print('''usage: {0} <command> [url]
url with sid, cid and cpid currently should be passed at least once to work
commands are:
init      initialize empty git repository
sync      update existing problem
add       add new problem
login     relogin if session is over
'''.format(path.basename(__file__)))
	exit(0)



'''
END UTILS
'''

data = {}

def get_or_panic(k):
	if k in data:
		return data[k]
	print('Key `{}` is necessary for this command'.format(k))
	exit(1)

dic = lambda *l: {k: data[k] for k in l if k in data}
cmdvals = lambda *l: (get_or_panic(k) for k in l)

def read_config(filename):
	try:
		global data
		data.update({k: v.strip() for k, v in 
			(l.split('=') for l in open(filename, 'r') if l)
			if v.strip()})
	except FileNotFoundError:
		pass

def write_config(filename, d):
	open(filename, 'w').write('\n'.join(("=".join((k, v)) for k, v in d.items() if v)))


def read_configs():
	read_config(path.join(path.expanduser('~'), RC_FILE))
	read_config(RC_FILE)
	data.update(gather_data(**data))

def write_configs():
	write_config(path.join(path.expanduser('~'), RC_FILE), dic('sid'))
	write_config(path.join(RC_FILE), dic('cid', 'cpid', 'download'))

def is_parsable(arg):
	f = arg.find
	return -1 < f('?') < f('=')

def extract_params(uri):
	global data
	data.update(uri_params(uri))
	data.update(gather_data(**data))

def parse_or_help(arg):
	extract_params(arg) if is_parsable(arg) else show_help()

def cmd_add_new_task():
	global data
	if 'cpid' not in data and 'download' not in data:
		add_new_task(*cmdvals('sid', 'cid'))
	else:
		print('Task already exist')

CMDS = {
	'init': init,
	'sync': lambda: update_repo(*cmdvals('sid', 'cid', 'cpid', 'download')),
	'add': cmd_add_new_task,
	'help': show_help,
	'login': lambda: data.update(dict(sid=login()))
}

if len(argv) > 3 or len(argv) == 1:
	show_help()

read_configs()

if len(argv) == 3:
	parse_or_help(argv[-1])
	CMDS.get(argv[1], show_help)()
else:
	CMDS.get(argv[1], lambda: parse_or_help(argv[1]))()

write_configs()