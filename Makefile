SHELL := /bin/bash

.PHONY: dev

# Create a temp dir for
export TMP_DIR:=$(shell mktemp -d)
# $(info TMP_DIR = ${TMP_DIR})
# $(shell { trap "if [ -z '${keep-temp}' ]; then rm -rf ${TMP_DIR}; echo Deleted ${TMP_DIR}; else echo DID NOT delete ${TMP_DIR}; fi" EXIT; tail --pid=$$PPID -f /dev/null; } \
# 	</dev/null >/dev/null 2>/dev/null &)


DEPLOY_FILES := $(shell find packages/*/deploy -type f)
CLONE_DIR := $(TMP_DIR)/clone
CLONE_GITIGNORE := $(CLONE_DIR)/.gitignore
# RANDOM_USERNAME:=norrin
RANDOM_USERNAME := $(shell shuf -zer -n10 {a..z} {A..Z} | tr -d '\0')
ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))

all:

start-docs: dev
	uv run mkdocs serve --dev-addr localhost:1111


dev:
	uv sync --group dev --all-packages


copier-%-prerequisites:
	@copier -v >/dev/null 2>&1 || { echo >&2 " 'copier' missing. will install"; uv tool install copier; }

	

new-project: copier-%-prerequisites
	@copier copy ./experimental/base-copier ./
	$(MAKE) dev
	@echo "Ensure to restart VSCode for imports to take hold"




shrinkwrap-%/rebuild/git-clone:
	@git clone . $(TMP_DIR)/clone

shrinkwrap-%/rebuild/build-gitignore: shrinkwrap-%/rebuild/git-clone
	@cat ./deploy/.gitignore >> $(CLONE_GITIGNORE)
	@echo "" >> $(CLONE_GITIGNORE)
	@cat packages/$(*)/deploy/.gitignore >> $(CLONE_GITIGNORE)
	@echo >> $(CLONE_GITIGNORE)

shrinkwrap-%/rebuild/rebuild-git: shrinkwrap-%/rebuild/build-gitignore
	@rm -rf $(CLONE_DIR)/.git
	@cd $(CLONE_DIR) && git init
	@cd $(CLONE_DIR) && \
		git config --local user.name "$(RANDOM_USERNAME)" && \
		git config --local user.email "$(RANDOM_USERNAME)@localhost.localdomain"

shrinkwrap-%/rebuild/git-commit-initial: shrinkwrap-%/rebuild/rebuild-git
	@cd $(CLONE_DIR) && \
		git add . && \
		git reset uv.lock && \
		git commit -m "Initial commit" --no-verify

shrinkwrap-%/rebuild/git-clean:	shrinkwrap-%/rebuild/git-commit-initial
	@cd $(CLONE_DIR) && \
		git clean -fdX

shrinkwrap-%/rebuild/relock: shrinkwrap-%/rebuild/git-clean
	@cd $(CLONE_DIR) && \
		uv lock && \
		git add uv.lock && \
		git commit --amend -m "Initial commit" --no-verify

shrinkwrap-%/rebuild/add-remote: shrinkwrap-%/rebuild/relock
	@cd $(CLONE_DIR) && \
		git remote add origin $(target-repo)

shrinkwrap-%/rebuild/qualitycheck: shrinkwrap-%/rebuild/add-remote
	@cd $(CLONE_DIR) && \
		test ! $$( find . \
			\( \
				-type f \
				-name '*.md' \
				-o \
				-name '*.ipynb' \
			\) \
			-o \
			\( \
				-type d \
				-name 'deploy' \
				-o \
				-name 'build' \
			\) \
			-print -quit | grep . )


shrinkwrap-%/rebuild: shrinkwrap-%/rebuild/qualitycheck
	@true

shrinkwrap-%/prerequisites:
	@# Must have a TMP_DIR var.
	@test ! -z "$(TMP_DIR)"
	@# Must have a directory at TMP_DIR
	@test -d "$(TMP_DIR)"
	@# Must know the target-user and target-repo
	@test ! -z "$(target-user)"
	@test ! -z "$(target-repo)"


shrinkwrap-%: shrinkwrap-%/prerequisites shrinkwrap-%/rebuild
	@echo $(ROOT_DIR)
	@echo $(CLONE_DIR)

# include packages/*/deploy/Makefile
