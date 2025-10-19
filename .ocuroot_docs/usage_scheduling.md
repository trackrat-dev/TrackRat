---
title: "Scheduling Work"
path: "usage/scheduling-work"
---

Through the course of changes to your source repos and updates to your intent store, Ocuroot will
need to execute various kinds of work to bring the current state into sync.

There are three main ways that work can happen in Ocuroot. Through creating releases, requesting
work, or triggering work.

This page will detail these mechanisms and the commands that can be used to configure them in CI.

## New Releases

New Releases will typically be created when code is merged into the main branch of a source repo.

A new Release is triggered via the command:

```bash
ocuroot release new path/to/release.ocu.star
```

This process is outlined in more detail on the [Releases](/docs/usage/releases) page.

As a result of [dependencies](usage/dependencies), a new release may cause additional work, such as
a new release of a backend service or ML model requiring upstream services to be redeployed to be
aware of the change. Providing the `--cascade` flag to `ocuroot release new` will result in this
additional work being executed automatically.

## Requesting Work

When a Release is created, it won't always be able to run to completion. Intent changes must
also be handled outside of a typical Release. This is where we need a mechanism to request
any outstanding work.

```bash
ocuroot work cascade
```

This command will inspect the state and intent stores, and identify any outstanding work that
can be executed across all source repos and commits. This work will then be executed.

A summary of the work to be executed can be provided with the `--dryrun` flag.