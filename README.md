CLI for [cats](http://imcs.dvfu.ru/cats). Currently only for jury

# Installation

- Install [python3](https://python.org) and [git](https://git-scm.com/)
- Clone this repository, install requirements, add cats.py to your PATH
```bash
git clone https://github.com/FooBarrior/cats-cli
pip install -r requirements.txt
ln -s cats.py ~/.local/bin/cats
```

# Running

`cats url`
`cats command [url]`

url with sid, cid and (cpid or download) currently should be passed at least once to work

This means, you can use either problem text url, or problem package url.

commands are:
```
init      initialize empty git repository
sync      update existing problem
add       add new problem
login     relogin if session is over
```

# Example

Creating new task:

```console
$ cats init 'mail.pl?f=problems;sid=314;cid=1592'
$ git commit problem.xml -m 'initial problem setting'
# trying to do this without modifications of problem.xml will result in problem reject,
# because xml dummy needs manual edition
$ cats add
```

Altering existing task:

```console
$ cats init 'mail.pl?f=problems;sid=314;cid=1592;cpid=6535'

# edit problem package

$ git commit -m 'edit problem'
$ cats sync
```