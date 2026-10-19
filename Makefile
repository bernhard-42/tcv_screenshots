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
	@gh release create v$(CURRENT_VERSION) --repo bernhard-42/tcv_screenshots --verify-tag \
		--title tcv_screenshots-$(CURRENT_VERSION) --notes v$(CURRENT_VERSION) \
		dist/tcv_screenshots-$(CURRENT_VERSION)-py3-none-any.whl \
		dist/tcv_screenshots-$(CURRENT_VERSION).tar.gz

upload:
	@twine upload dist/*
