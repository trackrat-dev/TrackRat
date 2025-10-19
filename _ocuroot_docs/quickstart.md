---
title: "Quickstart"
path: "quickstart"
---

Let's introduce you to the [Ocuroot client](https://github.com/ocuroot/ocuroot) by
building and deploying a set of interrelated services to a local Docker instance.

Through deploying these services, you'll see how Ocuroot manages missing dependencies, adding and populating new
environments and deleting environments.

Ordinarily, you may prefer to manage local containers with `docker compose`, but in this example, we'll be deploying
everything separately to illustrate how Ocuroot would operate in your datacenter or cloud environments.

## Prerequisites

You will need the following installed on your local machine:

* Docker
* Git
* Ocuroot client - see [installation instructions](https://github.com/ocuroot/ocuroot?tab=readme-ov-file#installation)

## Instructions

### 0. Clone the quickstart repository

We'll be working on a local copy of the quickstart repo, so you'll need to clone it.

```bash
git clone https://github.com/ocuroot/quickstart.git
cd quickstart
```

### 1. Create environments

Before we can deploy our services, we need somewhere to deploy them to. We need an environment.

For the quickstart, we have a config file that will do that for you, `environments.ocu.star`.

Kick off a release from that file to create a staging environment:

```bash
ocuroot release new environments.ocu.star
```

To get us started, this only creates a staging environment.
You can see the staging environment config by viewing the state:

```bash
$ ocuroot state get @/environment/staging
{
  "attributes": {
    "frontend_port": "8080",
    "type": "staging"
  },
  "name": "staging"
}
```

For the purposes of this quickstart, state is stored locally in the `.store` directory.

### 2. Release the frontend

Now we have an environment, we can release something to it. We'll start with the
"frontend" service.

```bash
ocuroot release new frontend/package.ocu.star
```

This should output something like this:

```bash
✓ build (30.399s)
  Outputs
  └── quickstart/-/frontend/package.ocu.star/@1/call/build#output/image
      └── quickstart-frontend:latest
› deploy to staging
  Pending Inputs
  └── quickstart/-/network/package.ocu.star/@/deploy/staging#output/network_name
```

The staging deployment has a pending input from `network/package.ocu.star`. This is
because we need a shared docker network for the staging environment.

### 3. Release network and complete frontend deployment

To satisfy the dependency for the frontend, we need to release the network.

```bash
ocuroot release new network/package.ocu.star --cascade
```

This will both create the network needed for the frontend, and then continue releasing the
frontend now that it is unblocked. The latter behavior is enabled by the `--cascade` flag.

The frontend should now be running and you can view it at http://localhost:8080. You'll see three
errors about unreachable services, this is because we need to deploy them!

### 4. Release backend services

Run these three commands to deploy the backend services.

```bash
ocuroot release new time-service/package.ocu.star
ocuroot release new weather-service/package.ocu.star
ocuroot release new message-service/package.ocu.star
```

Once complete, go back to the frontend and you'll see messages from these services.

### 4a. View state

We now have a fully populated staging environment! Ocuroot also includes a web UI to view your
state. You can start it by running:

```bash
ocuroot state view
```

This will start a local server showing the contents of your state store. Once started, open a browser to
http://localhost:3000 and take a look around.

### 5. Add a production environment

Now we have our staging environment fully populated and visually tested, we can
set up production!

Add the following to `environments.ocu.star`:

```star
register_environment(environment(
    name="production",
    attributes={
        "type": "production",
        "frontend_port": "8081",
    }
))
```

Then release these changes and deploy all services.

```bash
ocuroot release new environments.ocu.star --cascade
```

This will create the new production environment, and deploy all your release to it in
the correct order.

Once this is complete, you'll be able to load the production frontend at http://localhost:8081, 
there should be a line on the page indicating that the environment is "production".

### 6. Delete environments

You'll now have a bunch of containers running in your local Docker.
View the list by running:

```bash
docker ps -f name=^quickstart- --format "{{.Names}}"
```

You'll see containers for both production and staging.

Let's clean up after ourselves, first off, we'll delete our production environment.
First, let's delete the intent.

```bash
ocuroot state delete @/environment/production
```

This will update your intent for the production environment, but won't actually perform any actions.
In a typical deployment of Ocuroot, this change to intent will automatically trigger `ocuroot work cascade`
on your CI platform.

Now we can run `ocuroot work cascade` to actually perform the deletion, but first, let's look at what it's about
to do with the `--dryrun` flag.

```bash
ocuroot work cascade --dryrun
```

This outputs something like:

```json
[
  {
    "ref": "@/environment/staging",
    "work_type": "delete"
  }
]
```

Which indicates that we're going to delete the realized state of the staging environment, including
all resources.

So now we can execute all work required to remove this environment with a single command.

```bash
ocuroot work cascade
```

If you run the `docker ps` command above again, you'll only see the staging containers. 
See if you can adapt the above commands to delete the staging environment as well.

You can also look at the state with `ocuroot state view` and you will see that there are
no environments listed, although there is a full record of all historical deployments.

## Next steps

This was just a taste of what you can do with Ocuroot, and there's plenty more to explore even
within this repo! Feel free to have a look around to see how everything's configured. You could
also try:

* Deploying a change to the messages service
* Add multiple production environments with different names and ports