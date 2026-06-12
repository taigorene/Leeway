.PHONY: setup run test app

setup:
	./install.sh

run:
	./bin/leeway

test:
	.venv/bin/pytest -q

app:
	.venv/bin/pip install -q py2app
	rm -rf build dist
	.venv/bin/python setup.py py2app
