import requests
import subprocess
import getpass

from os import path
from itertools import chain
from zipfile import ZipFile

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
			print('git: ', e.output)
			exit(e.returncode)

	except FileNotFoundError as e:
		print('git: ', e.strerror)
		exit(e.errno)

	else:
		if soft:
			return output, 0
		else:
			return output


git_soft, git_hard = (
	lambda args: _git(args, soft=soft) 
		for soft in (True, False))


def init(taskfile=None):
	taskfile = taskfile || 'task.xml'
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

</Problem>
</CATS>''')
	open('.gitignore', 'w').writelines(['.gitignore', '*.zip', RC_FILE, '*.exe', 'a.out', '*.jar', '*.class'])

def get(rel_url, **params):
	params['json'] = '1'
	paramstr = ';'.join('='.join(i) for i in params.items())
	return requests.get('{}/{}?{}'.format(CATS_URL, rel_url, paramstr))

def post(rel_url, files=None, data=None):
	return requests.post(CATS_URL + '/' + rel_url, files={k: open(v, 'rb') for k, v in files}, data=data)

def login():
	print('Username: ', end='')
	usr = input()
	pwd = getpass.getpass()
	return get('main.pl', f='login', login=usr, passwd=pwd).json().get('sid')

def uri_params(uri):
	return dict(p.split('=') for p in uri.split('?')[-1].split(';'))

def prepare_zip():
	git_hard('archive -o task.zip')

def extract_console():
	ta_s = '<textarea cols="100" rows="10" readonly="readonly">'
	ta_e = '</textarea>'
	r = r[r.find(ta_s) + len(ta_s):]
	r = r[:r.find(ta_e)]
	return r


def update_repo(sid, cid, cpid, download):
	r = get('main.pl', f='problems', sid=sid, cid=cid, download=download)
	zip_file_name = r.url.split('/')[-1]
	with open(zip_file_name, 'wb') as f:
		f.write(r.content)

	git_status = git_hard('status --untracked -s'.split())

	if git_status:
		print("There are untracked files in work dir:")
		print(git_status)
		print("They may be unrecoverably overwriten by update.\nDo You want to continue? [y]n:")
		if input() not in 'yY':
			print('You may commit or stash files with git first, and then rerun command, or run `{}`'.format(PUSHALL_CMD))
			return

	ck_cmd = ['git', 'checkout']
	if subprocess.call('git rev-parse --verify ' + REMOTE_BRANCH):
		ck_cmd.append('--orphan')
	ck_cmd.append(REMOTE_BRANCH)

	git_hard(ck_cmd)

	with ZipFile(zip_file_name, 'r') as zf:
		zf.extractall()
		git_hard(['git', 'add'] + zf.namelist())

	git_hard(['git', 'commit', '-m', 'Update remote version'])

	git_hard('checkout master')
	git_hard('merge ' + REMOTE_BRANCH, shell=True)

	prepare_zip()

	r=post('main.pl',
		f='problems',
		files={'zip': 'task.zip'},
		replace="1",
		sid=sid,
		cid=cid,
		cpid=cpid).text
	
	print(extract_console(r))

def add_new_task():
	prepare_zip()

	r=post('main.pl',
		f='problems',
		files={'zip': 'task.zip'},
		add_new="1",
		sid=sid,
		cid=cid).text
	
	output = extract_console(r)

	S = 'Initialized empty Git repository in /srv/cats/cgi-bin/repos/'
	output = output[find(S):]
	repo = output[:find('/.git/')]

	global data
	data['download'] = repo

def show_help():
	print('''usage: {0} <command> [url]
url with sid, cid and cpid currently should be passed at least once to work
commands are:
init      initialize empty git repository
update    update existing problem
add       add new problem
login     relogin if session is over
''')
	exit(0)



'''
END UTILS
'''

data = {}

dic = lambda *l: {k: data[k] for k in l}
vals = lambda *l: (data[k] for k in l)

def read_config(file):
	return dict(l.split('=') for l in open('file', 'r'))

def write_config(file, dict):
	open(file, 'w').writelines(("=".join(k, v) for k, v in dict.items()))


def read_configs():
	global data
	data = {}
	data.update(read_config(path.join(path.expanduser('~'), RC_FILE)))
	data.update(read_config(RC_FILE))

def write_configs():
	global data
	write_config(path.join(path.expanduser('~'), RC_FILE), dic('sid')})
	write_config(path.join(RC_FILE), dic('cid', 'cpid', 'download')})

def is_parsable(arg):
	f = arg.find
	return -1 < f('?') < f('=')

def parse_or_help(arg):
	uri_params(args) if is_parsable(arg) else show_help()


CMDS = {
	'init': init,
	'update': lambda: update_repo(*vals('sid', 'cid', 'cpid', 'download'))
	'add': add_new_task
	'help': show_help
	'login': login
}

if len(argv) > 3 or len(argv) == 1:
	show_help()

if len(arg) == 3:
	parse_or_help(arg[-1])
	CMDS.get(arg[1], show_help)()
else:
	CMDS.get(arg[1], lambda: parse_or_help(arg[1]))()