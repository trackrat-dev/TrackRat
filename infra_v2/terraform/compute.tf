# Compute Configuration
# Instance template, MIG, and health check

# Container-Optimized OS image
data "google_compute_image" "cos" {
  family  = "cos-stable"
  project = "cos-cloud"
}

# Instance template
resource "google_compute_instance_template" "trackrat" {
  name_prefix  = "trackrat-${var.environment}-"
  machine_type = var.machine_type
  region       = var.region

  lifecycle {
    create_before_destroy = true
  }

  scheduling {
    preemptible                 = var.use_spot_vm
    automatic_restart           = !var.use_spot_vm
    on_host_maintenance         = var.use_spot_vm ? "TERMINATE" : "MIGRATE"
    provisioning_model          = var.use_spot_vm ? "SPOT" : "STANDARD"
    instance_termination_action = var.use_spot_vm ? "STOP" : null
  }

  disk {
    source_image = data.google_compute_image.cos.self_link
    auto_delete  = true
    boot         = true
    disk_size_gb = 25
  }

  network_interface {
    network = "default"
    access_config {}
  }

  service_account {
    email  = google_service_account.trackrat.email
    scopes = ["cloud-platform"]
  }

  tags = ["trackrat-${var.environment}"]

  metadata = {
    startup-script = <<-EOF
      #!/bin/bash
      set -e
      exec > /var/log/startup.log 2>&1

      echo "=== TrackRat ${var.environment} startup script ==="
      echo "Started at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

      # Configuration
      DISK_NAME="trackrat-${var.environment}-data"
      DISK_DEVICE="/dev/disk/by-id/google-$DISK_NAME"
      MOUNT_PATH="/mnt/disks/data"
      PROJECT_ID="${var.project_id}"
      ZONE="${var.zone}"
      REGION="${var.region}"
      ENVIRONMENT="${var.environment}"
      DEPLOY_BUCKET="${google_storage_bucket.deploy.name}"
      CONTAINER_IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/trackrat/api:$ENVIRONMENT-latest"

      # Get instance name from metadata
      INSTANCE_NAME=$(curl -s "http://metadata.google.internal/computeMetadata/v1/instance/name" -H "Metadata-Flavor: Google")
      echo "Instance: $INSTANCE_NAME"

      # ===========================================
      # 1. Attach and mount persistent disk
      # ===========================================
      echo "=== Attaching disk $DISK_NAME ==="
      if [ ! -e "$DISK_DEVICE" ]; then
        toolbox --quiet gcloud compute instances attach-disk "$INSTANCE_NAME" \
          --disk="$DISK_NAME" \
          --device-name="$DISK_NAME" \
          --zone="$ZONE" \
          --project="$PROJECT_ID" 2>/dev/null || true
      fi

      # Wait for disk to be attached
      echo "Waiting for disk..."
      for i in $(seq 1 60); do
        [ -e "$DISK_DEVICE" ] && break
        sleep 1
      done
      [ -e "$DISK_DEVICE" ] || { echo "ERROR: Disk not found after attach"; exit 1; }

      # Format disk if new
      if ! blkid "$DISK_DEVICE" > /dev/null 2>&1; then
        echo "Formatting new disk..."
        mkfs.ext4 -F "$DISK_DEVICE"
      fi

      # Mount disk
      echo "Mounting disk..."
      mkdir -p "$MOUNT_PATH"
      mountpoint -q "$MOUNT_PATH" || mount -o discard,defaults "$DISK_DEVICE" "$MOUNT_PATH"

      # Create data subdirectories
      mkdir -p "$MOUNT_PATH"/{pgdata,logs}
      echo "Disk mounted at $MOUNT_PATH"

      # ===========================================
      # 2. Install Docker Compose (standalone binary)
      # ===========================================
      # Note: CLI plugin approach doesn't work on COS because plugin paths are read-only
      # Using standalone binary with explicit DOCKER_CONFIG instead
      echo "=== Installing Docker Compose ==="
      COMPOSE_VERSION="2.24.0"
      COMPOSE_PATH="$MOUNT_PATH/bin/docker-compose"

      mkdir -p "$MOUNT_PATH/bin"
      if [ ! -f "$COMPOSE_PATH" ]; then
        curl -SL "https://github.com/docker/compose/releases/download/v$COMPOSE_VERSION/docker-compose-linux-x86_64" -o "$COMPOSE_PATH"
        chmod +x "$COMPOSE_PATH"
      fi
      echo "Docker Compose version: $($COMPOSE_PATH version)"

      # ===========================================
      # 3. Configure Docker authentication
      # ===========================================
      # On COS, /root is read-only so we use a writable path for Docker config
      # DOCKER_CONFIG must be set for both docker-credential-gcr and docker-compose
      echo "=== Configuring Docker auth ==="
      export DOCKER_CONFIG="$MOUNT_PATH/.docker"
      mkdir -p "$DOCKER_CONFIG"
      docker-credential-gcr configure-docker --registries=$REGION-docker.pkg.dev

      # ===========================================
      # 4. Fetch secrets from Secret Manager
      # ===========================================
      echo "=== Fetching secrets ==="
      DB_PASSWORD=$(toolbox --quiet gcloud secrets versions access latest \
        --secret=trackrat-db-password --project="$PROJECT_ID" 2>/dev/null)
      NJT_API_TOKEN=$(toolbox --quiet gcloud secrets versions access latest \
        --secret=trackrat-njt-api-token --project="$PROJECT_ID" 2>/dev/null)
      APNS_TEAM_ID=$(toolbox --quiet gcloud secrets versions access latest \
        --secret=trackrat-apns-team-id --project="$PROJECT_ID" 2>/dev/null)
      APNS_KEY_ID=$(toolbox --quiet gcloud secrets versions access latest \
        --secret=trackrat-apns-key-id --project="$PROJECT_ID" 2>/dev/null)
      APNS_BUNDLE_ID=$(toolbox --quiet gcloud secrets versions access latest \
        --secret=trackrat-apns-bundle-id --project="$PROJECT_ID" 2>/dev/null)
      echo "Secrets fetched successfully"

      # ===========================================
      # 5. Download docker-compose.yml from GCS
      # ===========================================
      echo "=== Downloading docker-compose.yml ==="
      APP_DIR="$MOUNT_PATH/compose"
      mkdir -p "$APP_DIR"
      # Download directly to compose dir - toolbox can access the mounted disk
      toolbox --quiet gsutil cp "gs://$DEPLOY_BUCKET/docker-compose.yml" "$APP_DIR/docker-compose.yml"

      # ===========================================
      # 6. Create .env file with configuration
      # ===========================================
      echo "=== Creating .env file ==="
      cat > "$APP_DIR/.env" <<ENVEOF
DATA_DIR=$MOUNT_PATH
IMAGE_URL=$CONTAINER_IMAGE
DB_PASSWORD=$DB_PASSWORD
NJT_API_TOKEN=$NJT_API_TOKEN
APNS_TEAM_ID=$APNS_TEAM_ID
APNS_KEY_ID=$APNS_KEY_ID
APNS_BUNDLE_ID=$APNS_BUNDLE_ID
APNS_ENVIRONMENT=prod
TRACKRAT_ENVIRONMENT=$ENVIRONMENT
TRACKRAT_LOG_LEVEL=INFO
ENVEOF
      chmod 600 "$APP_DIR/.env"

      # ===========================================
      # 7. Pull latest images and start containers
      # ===========================================
      echo "=== Starting containers ==="
      cd "$APP_DIR"

      # Stop existing containers (if any)
      $COMPOSE_PATH down 2>/dev/null || true

      # Pull latest images (DOCKER_CONFIG is exported, so compose uses it)
      $COMPOSE_PATH pull

      # Start containers
      $COMPOSE_PATH up -d

      echo ""
      echo "=== TrackRat started successfully ==="
      echo "Completed at: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    EOF

    # Graceful shutdown script for spot VM preemption
    # GCE gives 30 seconds warning - we use 25s timeout to leave buffer
    shutdown-script = <<-EOF
      #!/bin/bash
      echo "=== Shutdown initiated at $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a /var/log/shutdown.log

      APP_DIR="/mnt/disks/data/compose"
      COMPOSE_PATH="/mnt/disks/data/bin/docker-compose"

      if [ -f "$APP_DIR/docker-compose.yml" ] && [ -f "$COMPOSE_PATH" ]; then
        cd "$APP_DIR"
        # Stop containers gracefully (25s timeout leaves 5s buffer)
        $COMPOSE_PATH stop --timeout 25 2>&1 | tee -a /var/log/shutdown.log
        echo "Containers stopped" | tee -a /var/log/shutdown.log
      fi

      # Sync filesystem to flush PostgreSQL WAL
      sync

      echo "=== Shutdown complete at $(date -u +%Y-%m-%dT%H:%M:%SZ) ===" | tee -a /var/log/shutdown.log
    EOF

    google-logging-enabled = "true"
  }

  depends_on = [
    google_project_service.apis,
    google_artifact_registry_repository.trackrat,
    google_compute_disk.data,
    google_storage_bucket.deploy,
  ]
}

# Health check
resource "google_compute_health_check" "trackrat" {
  name = "trackrat-${var.environment}-health-check"

  http_health_check {
    port         = 8000
    request_path = "/health/live"
  }

  check_interval_sec  = 30
  timeout_sec         = 10
  healthy_threshold   = 2
  unhealthy_threshold = 3

  depends_on = [google_project_service.apis]
}

# Managed Instance Group
resource "google_compute_instance_group_manager" "trackrat" {
  name               = "trackrat-${var.environment}-mig"
  base_instance_name = "trackrat-${var.environment}"
  zone               = var.zone
  target_size        = 1

  version {
    instance_template = google_compute_instance_template.trackrat.self_link
  }

  named_port {
    name = "http"
    port = 8000
  }

  auto_healing_policies {
    health_check      = google_compute_health_check.trackrat.id
    initial_delay_sec = 300 # 5 minutes for migrations and startup
  }

  # For single-instance with persistent disk: delete old before creating new
  update_policy {
    type                  = "PROACTIVE"
    minimal_action        = "REPLACE"
    max_surge_fixed       = 0
    max_unavailable_fixed = 1
  }

  depends_on = [google_compute_instance_template.trackrat]
}
