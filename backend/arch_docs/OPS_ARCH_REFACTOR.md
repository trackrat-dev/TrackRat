# Operations Architecture Refactor Plan

## Executive Summary

This document outlines a comprehensive refactoring plan to modernize TrackRat's deployment architecture from a traditional VM-based approach to a cloud-native, declarative infrastructure on Google Cloud Platform (GCP). The goals are to improve scalability, reliability, maintainability, and developer experience while reducing operational overhead.

## Current State Analysis

### Architecture Overview
- **Deployment Model**: Single shared VM running both application and PostgreSQL database
- **Application Server**: Python FastAPI app served via Gunicorn with Uvicorn workers
- **Database**: PostgreSQL with manual administration
- **Configuration**: YAML files with environment-based selection
- **Deployment Process**: Manual, likely SSH-based deployment
- **Monitoring**: Basic health checks only
- **Environments**: Production only (no staging/test infrastructure)

### Key Pain Points
1. **Single Point of Failure**: VM hosts both app and database
2. **Manual Operations**: No infrastructure as code, manual deployments
3. **Limited Scalability**: Fixed VM resources, no auto-scaling
4. **Environment Management**: Difficult to create staging/test environments
5. **Observability Gaps**: Limited logging, no metrics or tracing
6. **Security Concerns**: Manual secret management, database on same VM
7. **Cost Efficiency**: Running VM 24/7 regardless of load

## Strategic Goals for Refactor

### Primary Goals
1. **Declarative Infrastructure**: Everything defined as code
2. **Environment Parity**: Easy creation of dev/staging/prod environments
3. **Scalability**: Auto-scale based on demand
4. **Reliability**: High availability, automated failover
5. **Security**: Defense in depth, managed secrets
6. **Cost Optimization**: Pay for what you use
7. **Developer Experience**: Self-service deployments, fast feedback

### Secondary Goals
1. **Observability**: Comprehensive logging, metrics, and tracing
2. **Disaster Recovery**: Automated backups, quick restoration
3. **Compliance**: Audit trails, data residency controls
4. **Performance**: Global edge caching, optimized data access
5. **Maintainability**: Clear separation of concerns, modular architecture

## Key Questions to Consider

### Business Requirements
1. **Traffic Patterns**: When are peak usage times? (likely rush hours)
2. **Availability Requirements**: What's acceptable downtime? 
3. **Data Retention**: How long to keep historical data?
4. **Geographic Distribution**: US-only or global access needed?
5. **Budget Constraints**: Monthly cloud spend targets?

### Technical Considerations
1. **State Management**: How to handle scheduler state across instances?
2. **Data Consistency**: How to ensure prediction model consistency?
3. **Migration Strategy**: Zero-downtime migration possible?
4. **Integration Points**: Any external systems depending on current IPs?
5. **Compliance**: Any regulatory requirements for train data?

### Operational Requirements
1. **Team Skills**: Who will manage the infrastructure?
2. **On-Call Rotation**: 24/7 support needed?
3. **Deployment Frequency**: How often do you deploy?
4. **Rollback Strategy**: How quickly can you revert changes?
5. **Access Control**: Who needs production access?

## Technical Proposal

### Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Google Cloud Platform                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐     ┌─────────────────┐    ┌──────────────┐ │
│  │   Cloud CDN  │────▶│  Load Balancer  │───▶│  Cloud Run   │ │
│  └──────────────┘     └─────────────────┘    │   Services   │ │
│                                               │              │ │
│                                               │ - API        │ │
│  ┌──────────────┐     ┌─────────────────┐   │ - Scheduler  │ │
│  │Cloud Storage │     │  Cloud SQL      │   │ - Workers    │ │
│  │   (Models)   │     │  (PostgreSQL)   │   └──────────────┘ │
│  └──────────────┘     └─────────────────┘                     │
│                                                                 │
│  ┌──────────────┐     ┌─────────────────┐    ┌──────────────┐│
│  │Secret Manager│     │Cloud Monitoring │    │Cloud Logging │ │
│  └──────────────┘     └─────────────────┘    └──────────────┘│
│                                                                 │
│  ┌──────────────┐     ┌─────────────────┐    ┌──────────────┐│
│  │  Pub/Sub     │     │Cloud Scheduler  │    │   Dataflow   ││
│  └──────────────┘     └─────────────────┘    └──────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. **Compute Layer - Cloud Run**
- **API Service**: Auto-scaling FastAPI instances
- **Scheduler Service**: Single instance with Cloud Scheduler triggers
- **Worker Services**: Background processing for data collection, predictions
- **Benefits**: 
  - Automatic HTTPS
  - Scale to zero capability
  - Built-in blue/green deployments
  - Per-request billing

#### 2. **Data Layer**
- **Cloud SQL**: Managed PostgreSQL with automatic backups
  - High availability configuration
  - Read replicas for analytics
  - Automatic maintenance windows
- **Cloud Storage**: ML models and static assets
  - Versioned model storage
  - Lifecycle policies for old models
  - CDN integration for fast model loading

#### 3. **Orchestration**
- **Cloud Scheduler**: Cron-based task triggers
- **Pub/Sub**: Decoupled service communication
- **Workflows**: Complex orchestration logic

#### 4. **Security**
- **Secret Manager**: Centralized secret storage
- **IAM**: Fine-grained access control
- **VPC**: Private networking for database
- **Cloud Armor**: DDoS protection

#### 5. **Observability**
- **Cloud Logging**: Structured logs with query capabilities
- **Cloud Monitoring**: Metrics, dashboards, and alerts
- **Cloud Trace**: Distributed tracing
- **Error Reporting**: Automatic error detection

### Infrastructure as Code

#### Terraform Structure
```
infrastructure/
├── environments/
│   ├── dev/
│   ├── staging/
│   └── prod/
├── modules/
│   ├── api/
│   ├── database/
│   ├── networking/
│   ├── monitoring/
│   └── security/
└── shared/
    ├── variables.tf
    └── outputs.tf
```

#### Key Terraform Modules

1. **API Module**
   - Cloud Run service configuration
   - Auto-scaling policies
   - Custom domains
   - Health checks

2. **Database Module**
   - Cloud SQL instance
   - Backup policies
   - Read replicas
   - Private IP configuration

3. **Networking Module**
   - VPC setup
   - Cloud NAT for outbound traffic
   - Private service connections
   - Load balancer configuration

4. **Monitoring Module**
   - Log sinks
   - Metrics and alerts
   - Dashboards
   - SLO tracking

5. **Security Module**
   - Secret Manager secrets
   - IAM bindings
   - Service accounts
   - Cloud Armor policies

### Application Changes Required

#### 1. **Containerization**
```dockerfile
# Multi-stage Dockerfile
FROM python:3.11-slim as builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY . .
CMD ["gunicorn", "trackcast.api.app:app", "--bind", "0.0.0.0:8080"]
```

#### 2. **Configuration Management**
```python
# Use environment variables with defaults
import os
from google.cloud import secretmanager

class CloudConfig:
    def __init__(self):
        self.project_id = os.environ.get('GCP_PROJECT_ID')
        self.secret_client = secretmanager.SecretManagerServiceClient()
    
    def get_secret(self, secret_id):
        name = f"projects/{self.project_id}/secrets/{secret_id}/versions/latest"
        response = self.secret_client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
```

#### 3. **Service Separation**
- Split monolithic scheduler into separate Cloud Run services
- Use Pub/Sub for inter-service communication
- Implement circuit breakers for external API calls

#### 4. **Database Connection Pooling**
```python
# Cloud SQL connection with Unix socket
from sqlalchemy import create_engine

def get_engine():
    if os.environ.get('GAE_ENV') == 'standard':
        # Production - use Unix socket
        db_socket_dir = os.environ.get("DB_SOCKET_DIR", "/cloudsql")
        cloud_sql_connection_name = os.environ["CLOUD_SQL_CONNECTION_NAME"]
        return create_engine(
            f"postgresql+pg8000://user:password@/{db_name}?"
            f"unix_sock={db_socket_dir}/{cloud_sql_connection_name}/.s.PGSQL.5432"
        )
    else:
        # Development - use TCP
        return create_engine(DATABASE_URL)
```

#### 5. **Structured Logging**
```python
import google.cloud.logging
import logging

# Set up structured logging
client = google.cloud.logging.Client()
client.setup_logging()

# Use structured fields
logging.info("Train data collected", extra={
    "train_id": train_id,
    "station": station_code,
    "event_type": "data_collection"
})
```

### Migration Roadmap

#### Phase 1: Foundation (Weeks 1-2)
1. **Set up GCP Project Structure**
   - Create dev, staging, prod projects
   - Configure billing and budgets
   - Set up IAM and service accounts

2. **Create Base Infrastructure**
   - Terraform modules for core resources
   - VPC and networking setup
   - Cloud SQL instance creation
   - Secret Manager configuration

3. **Containerize Application**
   - Create Dockerfile
   - Build CI/CD pipeline
   - Push to Artifact Registry

#### Phase 2: Database Migration (Week 3)
1. **Set up Cloud SQL**
   - Create instances in each environment
   - Configure backups and HA
   - Set up read replicas

2. **Migrate Data**
   - Export from current PostgreSQL
   - Import to Cloud SQL
   - Verify data integrity
   - Set up continuous replication for cutover

3. **Update Application Configuration**
   - Use Cloud SQL proxy for local development
   - Update connection strings
   - Test thoroughly

#### Phase 3: Application Deployment (Weeks 4-5)
1. **Deploy API Service**
   - Configure Cloud Run service
   - Set up custom domain
   - Configure auto-scaling
   - Set up health checks

2. **Deploy Background Services**
   - Scheduler service with Cloud Scheduler triggers
   - Data collection workers
   - Prediction generation workers

3. **Configure Networking**
   - Set up load balancer
   - Configure Cloud CDN
   - Set up Cloud Armor rules

#### Phase 4: Observability (Week 6)
1. **Logging and Monitoring**
   - Configure structured logging
   - Create custom metrics
   - Build dashboards
   - Set up alerts

2. **Error Tracking**
   - Configure Error Reporting
   - Set up PagerDuty integration
   - Create runbooks

3. **Performance Monitoring**
   - Set up Cloud Trace
   - Configure SLOs
   - Create performance dashboards

#### Phase 5: Advanced Features (Weeks 7-8)
1. **CI/CD Enhancement**
   - Cloud Build pipelines
   - Automated testing
   - Blue/green deployments
   - Rollback procedures

2. **Cost Optimization**
   - Set up committed use discounts
   - Configure auto-scaling policies
   - Implement caching strategies
   - Archive old data to Cloud Storage

3. **Security Hardening**
   - Security scanning
   - Vulnerability assessments
   - Penetration testing
   - Compliance documentation

#### Phase 6: Cutover and Validation (Week 9)
1. **Final Testing**
   - Load testing
   - Disaster recovery drills
   - Rollback testing
   - Performance validation

2. **Cutover**
   - DNS switch
   - Monitor closely
   - Quick rollback plan ready

3. **Post-Migration**
   - Decommission old infrastructure
   - Document lessons learned
   - Training for team

### Cost Estimation

#### Monthly Costs (Estimated)
- **Cloud Run**: $50-200 (based on traffic)
- **Cloud SQL**: $150-300 (HA instance)
- **Cloud Storage**: $10-20
- **Networking**: $20-50
- **Monitoring**: $10-30
- **Total**: $240-600/month

#### Cost Optimization Strategies
1. Use committed use discounts (up to 57% savings)
2. Right-size Cloud SQL during off-hours
3. Use Cloud CDN to reduce egress costs
4. Archive old data to Nearline storage
5. Set up budget alerts

### Risk Mitigation

#### Technical Risks
1. **Data Loss**: Automated backups, point-in-time recovery
2. **Service Outage**: Multi-zone deployment, health checks
3. **Cost Overrun**: Budget alerts, quotas, monitoring
4. **Security Breach**: Defense in depth, regular audits

#### Migration Risks
1. **Downtime**: Blue/green deployment, quick rollback
2. **Data Corruption**: Validation scripts, checksums
3. **Performance Issues**: Load testing, gradual rollout
4. **Team Knowledge**: Training, documentation, runbooks

### Success Metrics

#### Technical Metrics
- Deployment frequency: From weekly to multiple daily
- Lead time: From hours to minutes
- MTTR: From hours to minutes
- Availability: From 99% to 99.9%

#### Business Metrics
- Page load time: <2 seconds globally
- API response time: <200ms p95
- Cost per request: Reduced by 40%
- Developer productivity: Increased by 50%

### Next Steps

1. **Immediate Actions**
   - Review and approve this plan
   - Set up GCP organization and projects
   - Assign team members to phases
   - Create detailed project timeline

2. **Prerequisites**
   - GCP training for team
   - Terraform training
   - Set up development environments
   - Create proof of concept

3. **Quick Wins**
   - Containerize application
   - Set up CI/CD pipeline
   - Create development environment
   - Implement structured logging

## Conclusion

This refactoring will transform TrackRat from a traditional VM-based deployment to a modern, cloud-native architecture. The benefits include improved reliability, scalability, security, and developer experience, while potentially reducing operational costs through efficient resource utilization.

The phased approach minimizes risk while delivering value incrementally. Each phase builds upon the previous one, allowing for validation and adjustment along the way.

By embracing GCP's managed services and infrastructure as code, TrackRat will be positioned for future growth while reducing operational overhead.