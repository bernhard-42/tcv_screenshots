.PHONY: clean dist release create-release upload

CURRENT_VERSION := $(shell grep -m1 'version' pyproject.toml | cut -d'"' -f2)
PYCACHE := $(shell find . -name '__pycache__')
EGGS := $(wildcard *.egg-info)

clean:
	@echo "=> Cleaning"
	@rm -fr build dist $(EGGS) $(PYCACHE)

dist: clean
	@python -m build -n


release:
	git add .
	git status
	git diff-index --quiet HEAD || git commit -m "Latest release: $(CURRENT_VERSION)"
	git tag -a v$(CURRENT_VERSION) -m "Latest release: $(CURRENT_VERSION)"
	
create-release:
	@git push
	@git push --tags
	@github-release release -u bernhard-42 -r tcv_screenshots -t v$(CURRENT_VERSION) -n tcv_screenshots-$(CURRENT_VERSION)
	@sleep 2
	@github-release upload  -u bernhard-42 -r tcv_screenshots -t v$(CURRENT_VERSION) -n tcv_screenshots-$(CURRENT_VERSION)-py3-none-any.whl -f dist/tcv_screenshots-$(CURRENT_VERSION)-py3-none-any.whl
	@github-release upload  -u bernhard-42 -r tcv_screenshots -t v$(CURRENT_VERSION) -n tcv_screenshots-$(CURRENT_VERSION).tar.gz -f dist/tcv_screenshots-$(CURRENT_VERSION).tar.gz

upload:
	@twine upload dist/*
