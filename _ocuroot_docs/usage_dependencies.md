---
title: "Dependencies"
path: "usage/dependencies"
---

Once you have a few pipelines running to deploy infrastructure and services, they'll almost certainly
need to share data. Deploying a service may require details of the cluster where it is to be deployed.
A frontend serverless function may need to know the URL of a backend service. In an event driven system,
you may need to make sure the producer exists before the consumer.

To handle these challenges, Ocuroot allows you to define dependencies between release pipelines. Each Call
or Deployment has a set of Inputs and Outputs that can be connected with the Inputs and Outputs of others.

## Declaring Inputs

The `task` and `deploy` functions to declare Tasks accept an `inputs` parameter, which is a dictionary of
either static values, `ref`, or `input` objects.

For example, the below creates an input called `image_tag` that is populated from the `tag` output of the
most recent `build` call:

```python
task(
    security_scan,
    name="security_scan",
    inputs={
        "image_tag": ref("./@/task/build#output/tag"),
    },
)
```

The ref is declared as relative to the current config file. The fragment `#output/tag` will point directly to the
tag value in the outputs from this build. These outputs would have been returned from the build function:

```python
def build():
    # ...
    tag = "myapp:{}".format(build_number)
    return done(
        output={
            "tag": tag,
        }
    )
```

You can also declare `input` values with both a ref and a default value. This allows for a work item to refer to
itself.

```python
inputs={
    "prev_build_number": input(ref="./call/build#output/build_number", default=0),
},
```

Note the lack of an `@` portion in the ref above. This is because it is relative to the release where it is evaluated.

## Using inputs

Inputs are provided as arguments to the task function. For the task above, for example:

```python
def security_scan(image_tag):
    shell("scan.sh {}".format(image_tag))
    return done()
```

## How Dependencies are Resolved

After completing any work item, Ocuroot will check for any inputs that depend on its outputs. If the value of the output
is different than the most recent value for any existing deployments, they will be re-deployed with the new value.