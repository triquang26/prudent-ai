PYTHON := python3
DB := apt_engine.db

.PHONY: install show-w1 show-w2 show-w4 show-w6 show-w7 show-w8 show-w9 demo populate test clean

install:
	$(PYTHON) -m pip install -r requirements.txt -q

populate: install
	$(PYTHON) -m apt_engine.loaders.helm_lite $(DB)
	$(PYTHON) -m apt_engine.loaders.mlperf $(DB)
	$(PYTHON) -m apt_engine.loaders.routerbench $(DB)
	$(PYTHON) -m apt_engine.loaders.bfcl $(DB)
	$(PYTHON) -m apt_engine.loaders.mlenergy $(DB)
	$(PYTHON) -m apt_engine.loaders.beir_kilt $(DB)
	$(PYTHON) -m apt_engine.loaders.medhelm $(DB)
	$(PYTHON) -m apt_engine.loaders.hal $(DB)
	$(PYTHON) -m apt_engine.loaders.webarena $(DB)
	$(PYTHON) -m apt_engine.loaders.zenml_cases $(DB)
	$(PYTHON) -c "import sys; sys.path.insert(0,'src'); from apt_engine.profiles import seed_default_profiles; seed_default_profiles('$(DB)')"
	$(PYTHON) -m apt_engine.loaders._energy_supplement $(DB)
	@echo "DB populated."

show-w1: install
	@PYTHONPATH=src $(PYTHON) scripts/show_w1.py $(DB)

show-w2: install
	@PYTHONPATH=src $(PYTHON) scripts/show_w2.py $(DB)

show-w4: install
	@PYTHONPATH=src $(PYTHON) scripts/show_w4.py $(DB)

show-w6: install
	@PYTHONPATH=src $(PYTHON) scripts/show_w6.py $(DB)

show-w7: install
	@PYTHONPATH=src $(PYTHON) scripts/show_w7.py $(DB)

show-w8: install
	@PYTHONPATH=src $(PYTHON) scripts/show_w8.py $(DB)

show-w9: install
	@PYTHONPATH=src $(PYTHON) scripts/show_w9.py $(DB)

demo: install
	@PYTHONPATH=src $(PYTHON) scripts/demo.py $(DB)

test: install
	@PYTHONPATH=src $(PYTHON) -m pytest tests/ -v --tb=short

clean:
	rm -f $(DB)
	rm -f reports/coverage_report.md
