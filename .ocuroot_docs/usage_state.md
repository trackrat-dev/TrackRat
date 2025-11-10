---
title: "State"
path: "usage/state"
---

All state managed by Ocuroot is stored in JSON documents that are organized by Reference.

## Reference format

References are a URI-compatible string that serve as a path to a document within Ocuroot state.
They are of the form:

```
[repo]/-/[path]/@[release]/[subpath]#[fragment]
```

* `[repo]`: The URL or alias of a Git repo.
* `[path]`: The path to a file within the repo, usually a *.ocu.star file defining a Package.
* `[release]`: A release identifier. If blank, the most recent release is implied.
* `[subpath]`: A path to a document within the release, such as a deployment to a specific environment.
* `[fragment]`: An optional path to a field within the document.

For example, the following ref would refer to the container image for the first Release 
of the "frontend" Package in an example repo:

```
github.com/ocuroot/example/-/frontend/release.ocu.star/@r1/call/build#output/image
```

## State Storage

Details of where state is to be stored should be set in your `repo.ocu.star` file. You can use the same store
for both state and intent, or separate stores to help manage access. Typically, the state store should only
be modified by Ocuroot itself, while the intent store can be modified by users as they see fit.

Ocuroot supports both *filesystem* and *git* backends for state storage. Typically, you would use the
*filesystem* backend for testing your Ocuroot configuration, and the *git* backend to share state among
your team and CI system.

To configure a *filesystem* backend:

```python
store.set(
    store.fs(".store/state"),
    intent=store.fs(".store/intent"),
)
```

The paths provided are relative to the location of the `repo.ocu.star` file.

To configure a *git* backend:

```python
store.set(
    store.git("https://github.com/example/ocuroot-state.git", branch="state"),
    intent=store.git("https://github.com/example/ocuroot-state.git", branch="intent"),
)
```

## Working with state

State can be queried and manipulated using the `ocuroot state` commands. They are summarized here, but you
can also run `ocuroot state --help` for more information.

### ocuroot state get

The command `ocuroot state get` does what it says on the tin, it retrives the document at a specific ref.

Example:

```bash
$ ocuroot state get github.com/ocuroot/ocuroot/-/release.ocu.star/@/call/build_darwin_amd64
{
  "entrypoint": "github.com/ocuroot/ocuroot/-/release.ocu.star/@8/call/build_darwin_amd64/1/functions/1",
  "output": {
    "bucket_path": "ocuroot_binaries:client-binaries/ocuroot/0.3.9-3/darwin-amd64",
    "download_url": "https://downloads.ocuroot.com/ocuroot/0.3.9-3/darwin-amd64/ocuroot"
  },
  "release": "github.com/ocuroot/ocuroot/-/release.ocu.star/@8",
}

$ ocuroot state get github.com/ocuroot/ocuroot/-/release.ocu.star/@/call/build_darwin_amd64#output/download_url
"https://downloads.ocuroot.com/ocuroot/0.3.9-3/darwin-amd64/ocuroot"
```

### ocuroot state match

The `match` command lets you search for refs that match a specific glob pattern.

For example, to find all deployments to the `production environment`:

```bash
$ ocuroot state match "**/deploy/production"
```

### ocuroot state view

The `view` command starts a web UI for navigating Ocuroot state.

By default, the UI is hosted at [http://localhost:3000](http://localhost:3000).

![The state UI showing a release](/assets/docs/usage_state/state_view.png)

### ocuroot state set

The `set` command allows you to set the content of the document of a specific ref in the intent store.
This intent must then be applied to state via the `ocuroot state apply` or `ocuroot work any` commands. 

### ocuroot state delete

Similar to `ocuroot state set`, the `delete` command allows you to delete a document from the intent store.

## Types of state

### Environments

Environments are not associated with Repos, and are global to your state store.

An Environment ref is of the form:

```
@/environment/[name]
```

An Environment document must contain the same name as the ref, and a map of `attributes`.

You can create an environment from the command-line by setting the intent using the JSON format:

```bash
$ ocuroot state set -f=json "@/environment/production" '{"attributes": {"type": "prod"},"name": "production"}'
```

Once this intent is applied, the environment will be created and populated with any appropriate deployments.

You can also delete an environment with `ocuroot state delete`, which will destroy any deployments before removing the environment from state.

### Releases

Releases represent a point-in-time snapshot of a particular package and how it should be built and deployed.

A ref for a Release specifies its repo, path and release. For example:

```
github.com/ocuroot/example/-/path/to/package/release.ocu.star/@1
```    

The document at this ref defines the release process defined in the file `path/to/package/release.ocu.star` in the
repo `github.com/ocuroot/example` at release `1`. Release identifiers are monotonically increasing integers.

The commit hash for a specific release can be found in the commit subpath for the release:

```
github.com/ocuroot/example/-/path/to/package/release.ocu.star/@1/commit/[hash]
```

The hash is stored in the ref itself for quick lookup.
This allows you to look up the commit for a specific release:

```bash
$ ocuroot state match github.com/ocuroot/example/-/release.ocu.star/@r1/commit/*
```

Or even find all releases at a specific commit:

```bash
$ ocuroot state match github.com/ocuroot/example/-/**/@*/commit/fa56a23554a75a7ab334f841c5f61f952e52930c
github.com/ocuroot/example/-/frontend/release.ocu.star/@r1/commit/fa56a23554a75a7ab334f841c5f61f952e52930c
github.com/ocuroot/example/-/backend/release.ocu.star/@r1/commit/fa56a23554a75a7ab334f841c5f61f952e52930c
github.com/ocuroot/example/-/frontend/release.ocu.star/@r2/commit/fa56a23554a75a7ab334f841c5f61f952e52930c
```

Note that there can be multiple releases at a single commit.

### Tasks

Work within a Release is represented as Tasks below the Release Ref.

A basic Task represents a one-off step within a Release, like a build or test. Task refs are of the form:

```
github.com/ocuroot/example/-/path/to/package/release.ocu.star/@1/task/[name]
```

A Deployment is a special kind of task that represents a release of a package to a specific environment. Deployment refs are of the form:

```
github.com/ocuroot/example/-/path/to/package/release.ocu.star/@1/deploy/[environment]
```

Below Task Refs will be details of each Run. These are numbered sequentially
and will have a single status ref associated with them to make it easy to match against work with a specific result.

For example:

```
github.com/ocuroot/example/-/release.ocu.star/@r1/task/build/1/status/complete
```

Shows that the first execution of the build task in release r1 of the package at `release.ocu.star` was completed successfully.

The logs for this execution are also available at:

```
github.com/ocuroot/example/-/release.ocu.star/@r1/task/build/1/logs
```

### Custom State

Custom State provides a means to create and manage free-form data within your state. This can be useful
for requiring human approval to proceed in a Release, changing configuration of a deployment without having
to create a brand-new release or tracking information about teams.

Custom State may be stored globally:

```
@/custom/[name]
```

Or scoped to a specific release:

```
github.com/ocuroot/example/-/path/to/package/release.ocu.star/@r1/custom/[name]
```