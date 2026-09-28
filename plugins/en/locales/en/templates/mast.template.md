# MAST settings

Only the plugin's scripts read this file — `mast status` and the hooks. It is not loaded into
sessions' context: rules for the agent live in `.claude/rules/`, settings live here. A setting
is a `Key: value` line from the start of the line; without the line the default applies. Both
plugins, `mast` and `mast-ru`, understand the keys in English and in Russian.

## Dispatcher

Silence threshold: 30 min

`mast status` flags an item session with no new commit for longer than this. The flag blocks
nothing: a false alarm costs more than slow detection.

Restart threshold: 500k tokens

After `mast merge` a dispatcher whose context exceeds the threshold gets a hint: restart with
`/clear`. 500k is measured on a 1M window: auto-compaction there hits at 667k, and between
merges the context grew by up to 162k. For a model with a smaller window, set the threshold
below its auto-compaction.

## Prod

Shell commands the project considers prod: they go to a server, a data store, an experiment
tracker. The setting is the key `Prod` and patterns separated by commas; there may be several
such lines. A pattern is the start of the command as written in the project's files, up to
and including the resource name: the host, the bucket, the context. Or the project's own
script that goes to prod by itself. For example: `ssh gpu01`, `aws s3 cp s3://data-bucket`,
`DOCKER_CONTEXT=prod-vps`, `python scripts/launch_train.py`. There is no comma inside a
pattern. No such line — the project has declared no prod.
