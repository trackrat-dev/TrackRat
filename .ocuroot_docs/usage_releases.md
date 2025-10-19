---
title: "Releases"
path: "usage/releases"
---

Releases are one of the most important concepts in Ocuroot. They follow the process of going from
a commit in a Git repo to having your application deployed in all your desired environments.

The Release process for a Package is defined in a `*.ocu.star` file. This file is evaluated whenever work
is performed on a Release and describes the order of operations.

## Example Package File

```python
ocuroot("0.3.0")

def build(prev_build_number):
    build_number = prev_build_number + 1
    print("Building build {}...".format(build_number))
    tag = "myapp:{}".format(build_number)

    # Build a binary from source
    host.shell("docker build . -t {}".format(tag))
    # Push the build to a registry
    host.shell("docker push {}".format(tag))
    
    return done(
        output={
            "build_number": build_number,
            "tag": tag,
        }
    )

task(
    build, 
    name="build"
    inputs={
        # Get the build number from the most recent build, or start from 0
        # if there is no pre-existing build.
        "prev_build_number": input(ref="./@/call/build#output/build_number", default=0),
    }
)

def up(tag, environment):
    host.shell("./deploy.sh {} {}".format(tag, environment["name"]))
    host.shell("./test.sh {}".format(environment["name"]))
    return done()

def down(environment):
    host.shell("./undeploy.sh {}".format(environment["name"]))
    return done()

phase(
    "staging",
    tasks=[
       deploy(
            up=up,
            down=down,
            environment=e,
            inputs={
                # Get the tag from this build in this release
                "tag": input(ref="./call/build#output/tag"),
                
                # Note: The environment is passed in as a dictionary by default
            },
        # Deploy to all staging environments
        ) for e in environments() if e.attributes["type"] == "staging"
    ]
)

phase(
    "production",
    tasks=[
        deploy(
            up=up,
            down=down,
            environment=e,
            inputs={
                # Get the tag from this build in this release
                "tag": input(ref="./call/build#output/tag"),
            },
        # Deploy to all production environments
        ) for e in environments() if e.attributes["type"] == "prod"
    ]
)
```

In this example, we define a simple release process that builds a docker container, then deploys it to all staging
environments, followed by all production environments.

Work within phases is defined as either a `task`, which is not associated with an environment, or a `deploy`, which is.
It is assumed that deploy work is idempotent, and will replace any existing deployments for this config file within the specified environment.

Tasks have a `fn` function which is called to execute the task.

Deploys always have an `up` and `down` function, which define the steps to perform when deploying and undeploying to an environment.

These functions all receive parameters defined by the `inputs` dictionary of the task/deploy definition.

The `phase` function is a way to group together related work. Any work in a phase may execute in parallel. Each phase is executed in the order defined in the `*.ocu.star` file. If a `task` or `deploy` is defined outside of a
`phase`, it will be executed in-order as if it were in a phase with only one work item.

## Starting a New Release

A new release from a given Package file can be started by running:

```bash
ocuroot release new path/to/release.ocu.star
```

This will execute the Package file and create a new Release for the package at the current commit in the repo.

If there is already a Release for this commit, you can force the creation of a new one using the `--force` flag.

Work for this Release will then be executed in the appropriate order, assuming that all of the work's dependencies
are satisfied.

The work will continue to be executed until one of the following states is reached:

* The Release completes successfully
* A work item fails, resulting in failure of the Release as a whole
* A work item cannot proceed due to a missing dependency

When configuring Ocuroot to run on top of a CI platform, you would usually execute the 
`ocuroot release new` command for any appropriate files whenever a new commit is merged 
onto the main branch.

## Retrying a Failed Release

Sometimes, when a Release fails, the problem may be transient. This may be due to factors like an issue with a 
remote resource, or a missing local dependency.

In these cases, you can retry a failed Release by running:

```bash
ocuroot release retry path/to/release.ocu.star
```

Which will retry the failed work for the most recent Release of this Package.
You can also specify a Release explicitly:

```bash
ocuroot release retry path/to/release.ocu.star/@r1
```

Where `@r1` is the Release number in question.
