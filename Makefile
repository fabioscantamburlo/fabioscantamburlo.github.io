.PHONY: serve build stop

serve:
	uv run mkdocs serve --dirtyreload

build:
	uv run mkdocs build

stop:
	pkill -f "mkdocs serve" || true
