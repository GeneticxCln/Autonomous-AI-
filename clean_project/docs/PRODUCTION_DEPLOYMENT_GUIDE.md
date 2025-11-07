# 🚀 Production Deployment Guide

**Version:** 1.0.0
**Updated:** November 7, 2025
**Status:** Enterprise Ready

---

## 📋 **DEPLOYMENT OVERVIEW**

This guide provides comprehensive instructions for deploying the Autonomous Agent System in production environments using multiple deployment strategies.

### **Supported Deployment Methods**
1. **🐳 Docker Compose** - Simple single-host deployment
2. **☸️ Kubernetes** - Production-grade container orchestration
3. **🌐 Service Mesh** - Advanced networking with Istio
4. **☁️ Cloud Providers** - AWS, Azure, GCP deployment templates

---

## 🎯 **PREREQUISITES**

### **System Requirements**
- **OS:** Linux (Ubuntu 20.04+ recommended)
- **Memory:** 4GB minimum, 8GB+ recommended
- **CPU:** 2 cores minimum, 4+ cores recommended
- **Storage:** 20GB minimum SSD
- **Network:** 1Gbps+ recommended

### **Software Requirements**
```bash
# Core dependencies
Docker 20.10+
Docker Compose 2.0+
Python 3.9+
Git 2.20+
kubectl (for K8s deployment)
helm 3.0+ (optional)

# For development
Make 4.0+
```

### **Environment Setup**
```bash
# Clone repository
git clone <repository-url>
cd agent_monitor_system/clean_project

# Make scripts executable
chmod +x scripts/*.py
```

---

## 🐳 **DOCKER COMPOSE DEPLOYMENT**

### **Quick Start (Development)**
```bash
# Start all services
make infra-up

# Check status
make health

# View logs
make infra-logs

# Stop services
make infra-down
```

### **Production Configuration**
```bash
# Set production environment variables
export ENVIRONMENT=production
export JWT_SECRET_KEY="your-super-secret-jwt-key"
export API_DEBUG=false
export LOG_LEVEL=INFO

# Start with production configuration
docker-compose -f config/docker-compose.yml up -d

# Verify deployment
curl -f http://localhost:8000/health
```

### **Docker Compose Services**
| Service | Purpose | Port | Replicas |
|---------|---------|------|----------|
| `api` | Main application | 8000 | 3 |
| `redis` | Cache & message queue | 6379 | 1 |
| `worker_high` | High priority jobs | - | 2 |
| `worker_normal` | Normal jobs | - | 3 |
| `worker_low` | Low priority jobs | - | 1 |
| `nginx` | Load balancer | 80, 443 | 1 |
| `prometheus` | Metrics collection | 9090 | 1 |
| `grafana` | Monitoring dashboard | 3000 | 1 |
| `jaeger` | Distributed tracing | 16686 | 1 |

### **Custom Configuration**
Create `docker-compose.override.yml` for custom settings:
```yaml
version: '3.9'
services:
  api:
    environment:
      - CUSTOM_CONFIG=value
    volumes:
      - ./custom-data:/app/data
  redis:
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
```

---

## ☸️ **KUBERNETES DEPLOYMENT**

### **Prerequisites**
```bash
# Install kubectl
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
chmod +x kubectl
sudo mv kubectl /usr/local/bin/

# Verify installation
kubectl version --client
```

### **Deploy to Kubernetes**
```bash
# Set kubectl context
export KUBECONFIG=~/.kube/config

# Deploy all components
make k8s-deploy

# Check deployment status
make k8s-status

# View logs
make k8s-logs

# Check specific service
kubectl get pods -n agent-system
kubectl logs -l app=agent-system -n agent-system
```

### **Kubernetes Components**
```bash
# Namespace
kubectl get namespace agent-system

# ConfigMaps
kubectl get configmaps -n agent-system

# Deployments
kubectl get deployments -n agent-system

# Services
kubectl get services -n agent-system

# Ingress
kubectl get ingress -n agent-system

# Horizontal Pod Autoscaler
kubectl get hpa -n agent-system
```

### **Scaling**
```bash
# Scale API deployment
kubectl scale deployment agent-api --replicas=5 -n agent-system

# Scale workers
kubectl scale deployment agent-worker-normal --replicas=5 -n agent-system

# Check HPA status
kubectl get hpa -n agent-system
```

### **Monitoring**
```bash
# Port forward to access services locally
kubectl port-forward svc/agent-api-service 8000:8000 -n agent-system
kubectl port-forward svc/grafana-service 3000:3000 -n agent-system
kubectl port-forward svc/prometheus-service 9090:9090 -n agent-system
```

---

## 🌐 **SERVICE MESH DEPLOYMENT**

### **Istio Installation**
```bash
# Install Istio
curl -L https://istio.io/downloadIstio | sh -
cd istio-*
export PATH=$PWD/bin:$PATH

# Install Istio with custom configuration
istioctl install -f k8s/istio/istio-config.yaml
```

### **Deploy with Service Mesh**
```bash
# Deploy gateway configuration
kubectl apply -f k8s/istio/gateway.yaml

# Deploy security policies
kubectl apply -f k8s/security/peer-authentication.yaml

# Verify service mesh
kubectl get pods -n istio-system
istioctl proxy-status
```

### **Service Mesh Features**
- **mTLS Encryption:** Automatic service-to-service encryption
- **Load Balancing:** Intelligent traffic management
- **Circuit Breaking:** Automatic failure handling
- **Tracing:** Distributed request tracing
- **Security Policies:** Fine-grained access control

---

## ☁️ **CLOUD PROVIDER DEPLOYMENT**

### **AWS Deployment**

#### **Prerequisites**
```bash
# Install AWS CLI
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
unzip awscliv2.zip
sudo ./aws/install

# Configure AWS credentials
aws configure
```

#### **EKS Deployment**
```bash
# Create EKS cluster
eksctl create cluster \
  --name agent-system \
  --version 1.27 \
  --region us-west-2 \
  --nodegroup-name workers \
  --node-type t3.medium \
  --nodes 3 \
  --nodes-min 2 \
  --nodes-max 5 \
  --managed

# Update kubeconfig
aws eks update-kubeconfig --region us-west-2 --name agent-system

# Deploy application
make k8s-deploy
```

#### **RDS Database (PostgreSQL)**
```bash
# Create RDS instance
aws rds create-db-instance \
  --db-instance-identifier agent-system-db \
  --db-instance-class db.t3.micro \
  --engine postgres \
  --master-username admin \
  --master-user-password YourSecurePassword123 \
  --allocated-storage 20 \
  --vpc-security-group-ids sg-xxxxxxxxx

# Update database URL in ConfigMap
kubectl patch configmap agent-config -n agent-system \
  --patch '{"data":{"DATABASE_URL":"postgresql://admin:YourSecurePassword123@your-rds-endpoint:5432/agent_system"}}'
```

#### **ElastiCache (Redis)**
```bash
# Create ElastiCache cluster
aws elasticache create-cache-cluster \
  --cache-cluster-id agent-system-redis \
  --cache-node-type cache.t3.micro \
  --engine redis \
  --num-cache-nodes 1 \
  --cache-subnet-group-name default \
  --vpc-security-group-ids sg-xxxxxxxxx

# Update Redis URL
kubectl patch configmap agent-config -n agent-system \
  --patch '{"data":{"REDIS_URL":"redis://your-elasticache-endpoint:6379/0"}}'
```

### **Azure Deployment**

#### **AKS Deployment**
```bash
# Create resource group
az group create --name agent-system-rg --location eastus

# Create AKS cluster
az aks create \
  --resource-group agent-system-rg \
  --name agent-system \
  --node-count 3 \
  --node-vm-size Standard_D2s_v3 \
  --generate-ssh-keys \
  --enable-addons monitoring

# Get credentials
az aks get-credentials \
  --resource-group agent-system-rg \
  --name agent-system

# Deploy application
make k8s-deploy
```

### **GCP Deployment**

#### **GKE Deployment**
```bash
# Create project and enable APIs
gcloud projects create agent-system --name="Agent System"
gcloud config set project agent-system
gcloud services enable container.googleapis.com

# Create cluster
gcloud container clusters create agent-system \
  --zone us-central1-a \
  --num-nodes 3 \
  --machine-type n1-standard-2 \
  --enable-autoscaling \
  --min-nodes 2 \
  --max-nodes 10

# Get credentials
gcloud container clusters get-credentials agent-system --zone us-central1-a

# Deploy application
make k8s-deploy
```

---

## 🔒 **SECURITY CONFIGURATION**

### **SSL/TLS Certificates**
```bash
# Generate self-signed certificates (development)
mkdir -p ssl
openssl req -x509 -newkey rsa:4096 -keyout ssl/key.pem -out ssl/cert.pem -days 365 -nodes

# For production, use Let's Encrypt
certbot certonly --standalone -d your-domain.com

# Update Nginx configuration
kubectl create secret tls agent-tls-secret \
  --cert=path/to/cert.pem \
  --key=path/to/key.pem \
  -n agent-system
```

### **Secrets Management**
```bash
# Create secrets
kubectl create secret generic agent-secrets \
  --from-literal=jwt-secret-key="your-jwt-secret" \
  --from-literal=openai-api-key="your-openai-key" \
  --from-literal=anthropic-api-key="your-anthropic-key" \
  -n agent-system

# Create encrypted secrets (recommended)
echo -n "your-secret" | kubectl create secret generic mysecret --dry-run=client -o yaml --from-file=secret=/dev/stdin - | \
kubectl apply -f -
```

### **Network Policies**
```bash
# Apply network policies
kubectl apply -f k8s/security/network-policies.yaml
```

---

## 📊 **MONITORING & OBSERVABILITY**

### **Grafana Configuration**
```bash
# Access Grafana
kubectl port-forward svc/grafana-service 3000:3000 -n agent-system

# Default credentials
Username: admin
Password: admin (change on first login)

# Import dashboards
kubectl apply -f config/monitoring/grafana/dashboards/
```

### **Prometheus Configuration**
```bash
# Access Prometheus
kubectl port-forward svc/prometheus-service 9090:9090 -n agent-system

# Check metrics
curl http://localhost:9090/metrics
```

### **Jaeger Configuration**
```bash
# Access Jaeger UI
kubectl port-forward svc/jaeger-service 16686:16686 -n agent-system

# View traces in browser
http://localhost:16686
```

---

## 🚨 **HEALTH CHECKS**

### **Application Health**
```bash
# API health check
curl -f http://localhost:8000/health

# Detailed health
curl -f http://localhost:8000/api/v1/system/health
```

### **Infrastructure Health**
```bash
# Redis health
docker exec agent_redis redis-cli ping
# Or
kubectl exec -it deployment/redis -n agent-system -- redis-cli ping

# Database health
sqlite3 agent_enterprise.db ".tables"

# Check all services
make health
```

### **Kubernetes Health**
```bash
# Check all resources
kubectl get all -n agent-system

# Check events
kubectl get events -n agent-system --sort-by='.lastTimestamp'

# Check resource usage
kubectl top pods -n agent-system
kubectl top nodes
```

---

## 🔄 **BACKUP & RECOVERY**

### **Database Backup**
```bash
# Manual backup
docker exec agent_api sqlite3 /app/data/agent_enterprise.db ".backup /app/backups/backup-$(date +%Y%m%d-%H%M%S).db"

# Automated backup (configured in docker-compose)
# Check backup status
docker logs agent_db_backup
```

### **Kubernetes Backup**
```bash
# Backup all resources
kubectl get all,configmaps,secrets,pvc -n agent-system -o yaml > agent-system-backup.yaml

# Use velero for production backup
velero install --provider aws --plugins velero/velero-plugin-for-aws:v1.2.0
velero backup create agent-system-backup --include-namespaces agent-system
```

### **Redis Backup**
```bash
# Redis RDB backup
docker exec agent_redis redis-cli BGSAVE

# Copy backup file
docker cp agent_redis:/data/dump.rdb ./backups/redis-backup.rdb
```

---

## 📈 **PERFORMANCE TUNING**

### **Database Optimization**
```sql
-- SQLite optimizations
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = 10000;
PRAGMA temp_store = memory;
PRAGMA mmap_size = 268435456;
```

### **Redis Optimization**
```bash
# Redis configuration in docker-compose
command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru --save 900 1 --save 300 10 --save 60 10000
```

### **Application Optimization**
```bash
# Enable caching
export ENABLE_CACHING=true
export CACHE_TTL=1800

# Enable rate limiting
export ENABLE_RATE_LIMITING=true
export RATE_LIMIT_REQUESTS=100

# Tune worker processes
export WORKER_CONCURRENCY=4
```

### **Load Testing**
```bash
# Run performance benchmarks
python scripts/performance_benchmark.py

# Custom load test
k6 run tests/load/test-api.js
```

---

## 🛠️ **TROUBLESHOOTING**

### **Common Issues**

#### **Service Not Starting**
```bash
# Check logs
docker logs <container-name>
kubectl logs <pod-name> -n agent-system

# Check events
kubectl get events -n agent-system --sort-by='.lastTimestamp'

# Check resource limits
kubectl describe pod <pod-name> -n agent-system
```

#### **Database Connection Issues**
```bash
# Test database connection
kubectl exec -it deployment/agent-api -n agent-system -- python -c "import sqlite3; print('OK')"

# Check database file
kubectl exec -it deployment/agent-api -n agent-system -- ls -la /app/data/
```

#### **Redis Connection Issues**
```bash
# Test Redis connection
kubectl exec -it deployment/redis -n agent-system -- redis-cli ping

# Check Redis logs
kubectl logs deployment/redis -n agent-system
```

#### **Memory Issues**
```bash
# Check memory usage
kubectl top pods -n agent-system
docker stats

# Check for memory leaks
kubectl describe pod <pod-name> -n agent-system | grep -A 10 "Limits\|Requests"
```

### **Debug Mode**
```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
export API_DEBUG=true

# Restart services
make infra-down
make infra-up
```

---

## 📞 **SUPPORT & MAINTENANCE**

### **Regular Maintenance**
```bash
# Weekly tasks
- Check system health
- Review security logs
- Update dependencies
- Backup database

# Monthly tasks
- Security audit
- Performance review
- Capacity planning
- Update documentation
```

### **Log Rotation**
```bash
# Configure log rotation
docker run --rm -v /var/log:/var/log logrotate logrotate /etc/logrotate.conf

# Kubernetes log rotation
kubectl set env deployment/agent-api LOG_ROTATION=true -n agent-system
```

### **Updates & Upgrades**
```bash
# Update application
git pull origin main
make build
make deploy

# Update dependencies
make update-deps

# Update security patches
make security-update
```

---

## 🎯 **PRODUCTION CHECKLIST**

### **Security**
- [ ] SSL/TLS certificates installed
- [ ] JWT secrets rotated
- [ ] API keys secured
- [ ] Network policies applied
- [ ] RBAC configured
- [ ] Security scanning completed

### **Monitoring**
- [ ] Grafana dashboards configured
- [ ] Alerting rules set up
- [ ] Log aggregation working
- [ ] Performance monitoring active
- [ ] Health checks configured

### **Reliability**
- [ ] Database backups automated
- [ ] Auto-scaling configured
- [ ] Circuit breakers enabled
- [ ] Rate limiting active
- [ ] Load balancing working

### **Performance**
- [ ] Caching enabled
- [ ] Database optimized
- [ ] Resources allocated
- [ ] Load testing completed
- [ ] Performance benchmarks met

### **Documentation**
- [ ] Deployment guide followed
- [ ] Runbooks created
- [ ] Contact information updated
- [ ] Incident procedures documented
- [ ] Training completed

---

## 📚 **ADDITIONAL RESOURCES**

### **Documentation**
- [API Documentation](http://localhost:8000/docs)
- [Architecture Guide](ARCHITECTURE.md)
- [Security Guide](SECURITY.md)
- [Performance Guide](PERFORMANCE.md)

### **External Resources**
- [Docker Documentation](https://docs.docker.com/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Istio Documentation](https://istio.io/latest/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

### **Support Channels**
- **GitHub Issues:** For bug reports and feature requests
- **Documentation:** See `/docs` directory
- **Monitoring:** Access Grafana at http://localhost:3000
- **Logs:** Check application logs via `make infra-logs`

---

**🎉 Your Autonomous Agent System is now production-ready!**

For support or questions, please refer to the troubleshooting section or create a GitHub issue.
