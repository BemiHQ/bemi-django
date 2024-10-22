setup:
	python3 -m venv venv

install:
	source ./venv/bin/activate && \
	pip install --upgrade twine && \
	pip install --upgrade build

build:
	source ./venv/bin/activate && \
	python -m build && \
	twine check dist/*

publish:
	source ./venv/bin/activate && \
	python -m twine upload dist/*	