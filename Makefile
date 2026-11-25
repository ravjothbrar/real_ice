PY ?= python3
.PHONY: test setup fetch grid thickness growth retention survival export web all
setup:      ; $(PY) -m pip install -r requirements.txt
test:       ; $(PY) -m pytest -q eval/tests
fetch:      ; $(PY) -m pipeline.fetch.all
grid:       ; $(PY) -m pipeline.grid
thickness:  ; $(PY) -m pipeline.thickness
growth:     ; $(PY) -m pipeline.growth
retention:  ; $(PY) -m pipeline.retention
survival:   ; $(PY) -m pipeline.survival
hindcast:   ; $(PY) -m eval.hindcast
export:     ; $(PY) -m pipeline.export
web:        ; cd web && npm install && npm run build
all: grid thickness growth retention survival hindcast export
