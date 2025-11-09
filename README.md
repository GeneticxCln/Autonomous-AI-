# 🤖 Autonomous AI Agent System

> Note: The canonical, production-ready project lives in `clean_project/`. Root-level Dockerfile/Makefile/requirements are legacy. Use `clean_project/Makefile` and `clean_project/config/Dockerfile`.

<div align="center">

![Agent System](https://img.shields.io/badge/AI-Agent%20System-blue)
![Python](https://img.shields.io/badge/Python-3.9+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-Latest-green)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-orange)
![License](https://img.shields.io/badge/License-MIT-yellow)

**Enterprise-grade autonomous AI agent platform with real intelligence, learning capabilities, and production-ready infrastructure**

[![API Documentation](https://img.shields.io/badge/API-Documentation-blue)](http://localhost:8000/docs)
[![Health Check](https://img.shields.io/badge/Health-Check-green)](http://localhost:8000/health)
[![Performance](https://img.shields.io/badge/Performance-Sub--10ms-brightgreen)](#-performance)

</div>

## ✨ Key Features

### 🧠 **True AI Intelligence**
- **Autonomous Reasoning**: Advanced planning and decision-making capabilities
- **Cross-Session Learning**: Persistent knowledge accumulation across sessions
- **Dynamic Adaptation**: Learns from experience and improves over time
- **Goal-Oriented Planning**: Intelligent task decomposition and execution

### 🔐 **Enterprise Security**
- **JWT Authentication**: Stateless, secure token-based authentication
- **Role-Based Access Control**: 4-tier permission system (admin, manager, user, guest)
- **Account Security**: Lockout protection, audit trails, and failed attempt tracking
- **API Security**: Rate limiting, CORS protection, and security headers

### 🌐 **Multiple Interfaces**
- **FastAPI Web Interface**: Interactive dashboard with real-time monitoring
- **RESTful API**: Complete CRUD operations for all entities
- **Interactive CLI**: Chat-based and terminal interfaces
- **Background Worker Service**: Dedicated queue consumer (`python -m agent_system.worker`)
- **Comprehensive Documentation**: OpenAPI 3.0 with examples and schemas

### 🛠️ **Advanced Tool System**
- **Real & Mock Tools**: Automatic fallback for reliable operation
- **Plugin Architecture**: Extensible tool ecosystem
- **API Integration**: Support for external services (OpenAI, Anthropic, etc.)
- **Security Validation**: Safe execution environment

### 📊 **Performance & Monitoring**
- **Real-time Metrics**: Performance monitoring and health checks
- **Audit Logging**: Comprehensive security event tracking
- **Database Optimization**: Efficient SQLAlchemy models with indexing
- **Production Ready**: Docker deployment with health checks

### 🕸️ **Distributed Architecture**
- **Cluster Message Bus**: Priority-aware queue with Redis backend and in-memory fallback for cross-node agent messaging
- **Service Discovery**: Self-registering FastAPI and worker services with TTL heartbeats for automatic discovery
- **Distributed State**: Shared state manager with optimistic versioning for workflow progress and cluster health snapshots
- **Resilience Features**: Automatic retry/rescue of stale messages plus service cleanup to keep the cluster consistent
- **Portable Workers**: Launch additional consumers via `make worker` to scale background processing

## 🚀 Quick Start

### Prerequisites
- Python 3.9 or higher
- SQLite (default) or PostgreSQL for production
- Optional: API keys for enhanced AI capabilities

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd agent

# (Optional) Create an isolated environment with all dev tooling
make venv
source .venv/bin/activate

# Quick setup with the clean, production-ready version
cd clean_project

# Install dependencies
make install

# Set up environment
cp .env.example .env
# Edit .env with your configuration

# Initialize the system
make setup

# Run the agent
make run

# Start the asynchronous worker that processes queued jobs (needs Redis + DISTRIBUTED_ENABLED=true)
make worker
```

### Alternative: Development Setup

```bash
# Install from main directory (development version)
cd /path/to/agent

# Install all dependencies
pip install -r requirements.txt

# Initialize authentication system
python -c "from agent_system.auth_service import auth_service; from agent_system.auth_models import db_manager; db_manager.initialize(); auth_service.initialize()"

# Run the FastAPI server
python -m agent_system.fastapi_app --host 0.0.0.0 --port 8000
```

### Web Interface Access

Once running, access the system at:
- **🌐 Main Dashboard**: http://localhost:8000
- **📚 API Documentation**: http://localhost:8000/docs
- **🔍 ReDoc Interface**: http://localhost:8000/redoc
- **❤️ Health Check**: http://localhost:8000/health
- **ℹ️ API Information**: http://localhost:8000/api/info

## 📁 Project Structure

```
agent/
├── 📁 clean_project/              # 🎯 Production-ready version (recommended)
│   ├── src/agent_system/          # Core agent modules
│   │   ├── agent.py              # Main autonomous agent
│   │   ├── ai_planner.py         # AI planning engine
│   │   ├── action_selector.py    # Decision making system
│   │   ├── cross_session_learning.py  # Learning system
│   │   ├── auth_service.py       # Enterprise authentication
│   │   ├── api_endpoints.py      # FastAPI endpoints
│   │   ├── api_schemas.py        # Comprehensive OpenAPI schemas
│   │   ├── database_models.py    # SQLAlchemy models
│   │   ├── enhanced_agent.py     # Enhanced agent capabilities
│   │   ├── chat_cli.py           # Interactive chat interface
│   │   └── ...                   # More modules
│   ├── tests/                    # Comprehensive test suite
│   ├── scripts/                  # Utilities and demos
│   ├── config/                   # Configuration and deployment
│   ├── docs/                     # Documentation
│   ├── Makefile                  # Development commands
│   ├── pyproject.toml           # Project configuration
│   └── README.md                # Clean project documentation
│
├── 📁 agent_system/              # Development version (extensive features)
│   ├── auth_service.py          # Authentication system
│   ├── api_endpoints.py         # API endpoints
│   ├── api_schemas.py           # Comprehensive schemas
│   ├── auth_models.py           # Auth models
│   ├── fastapi_app.py           # FastAPI application
│   ├── production_config.py     # Production configuration
│   ├── security_hardening.py    # Security features
│   └── ...                      # More development files
│
├── 📁 scripts/                   # Development utilities
│   ├── test_comprehensive_auth.py      # Auth testing
│   ├── test_api_documentation.py       # API docs testing
│   ├── enterprise_demo.py              # Enterprise features demo
│   └── ...                            # More scripts
│
├── 📁 .agent_state/              # Agent state and memory
├── 📁 .agent_monitoring/         # Performance monitoring
├── 📁 clean_project/             # Database files
├── agent_enterprise.db          # Main database
├── requirements.txt             # Dependencies
├── .env.example                # Environment template
├── API_DOCUMENTATION_IMPROVEMENTS.md  # API improvements summary
└── README.md                   # This file
```

## 🎯 Core Components

### AI Intelligence Layer
- **AutonomousAgent**: Central orchestrator with goal management
- **AI Planner**: Intelligent task decomposition and planning
- **Action Selector**: Smart decision making with confidence scoring
- **Learning System**: Experience-based improvement and adaptation
- **Cross-Session Memory**: Persistent knowledge across sessions

### Authentication & Security
- **JWT Authentication**: Stateless token-based security
- **Role-Based Access Control**: Granular permission system
- **Session Management**: Secure session handling with refresh tokens
- **API Token System**: Programmatic access with scope-based permissions
- **Security Audit Trail**: Comprehensive event logging

### Web Interface
- **FastAPI Backend**: High-performance async web framework
- **Interactive Documentation**: OpenAPI 3.0 with examples
- **Real-time Health Monitoring**: System status and performance
- **CORS Protection**: Secure cross-origin resource sharing
- **Rate Limiting**: DDoS protection and fair usage

### Tool System
- **Enhanced Tool Registry**: Real/mock tool support
- **Plugin Architecture**: Extensible tool ecosystem
- **API Integration**: External service support
- **Security Validation**: Safe execution environment

## 🛠️ Development

### Available Commands (Clean Project)

```bash
# Setup and Installation
make install          # Install dependencies
make dev             # Development installation
make setup           # Initialize system

# Development Workflow
make lint            # Code linting
make format          # Code formatting
make typecheck       # Type checking
make test            # Run tests
make cov            # Test coverage
make ci             # Full CI pipeline

# Running the System
make run            # Run agent with default goals
make interactive    # Interactive terminal mode
make web            # Web dashboard
make api            # API server
make chat           # Chat interface
```

### Development Setup (Main Directory)

```bash
# Install dependencies
pip install -r requirements.txt

# Run specific components
python -m agent_system.fastapi_app --port 8000
python -c "from agent_system.chat_cli import main; main()"
python scripts/enterprise_demo.py

# Run tests
pytest test_comprehensive_auth.py -v
pytest test_api_documentation.py -v
```

## 🔧 Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Core Settings
MAX_CYCLES=100
LOG_LEVEL=INFO
ENVIRONMENT=development

# Security (Required for production)
JWT_SECRET_KEY=your-super-secret-jwt-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Database
DATABASE_URL=sqlite:///./agent_enterprise.db
# For production: postgresql://user:pass@localhost:5432/db

# API Keys (Optional - for enhanced AI)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
SERPAPI_KEY=your_serpapi_key

# Security Settings
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60
MAX_LOGIN_ATTEMPTS=5
ACCOUNT_LOCKOUT_DURATION=30

# Performance
ENABLE_RATE_LIMITING=true
ENABLE_CACHING=true
ENABLE_AUDIT_LOGGING=true
```

### Production Configuration

For production deployment:

```bash
# Security
export JWT_SECRET_KEY="your-production-secret"
export ENVIRONMENT="production"
export SECURE_HEADERS="true"
export ENABLE_HTTPS="true"

# Database
export DATABASE_URL="postgresql://user:pass@prod-db:5432/agent"

# Monitoring
export ENABLE_METRICS="true"
export METRICS_PORT="9090"
```

## 📖 API Documentation

### Authentication Flow

1. **Login** to get access and refresh tokens
2. **Use access token** in Authorization header for API calls
3. **Refresh token** when access token expires
4. **Logout** to invalidate session

### Example API Usage

```bash
# 1. Login
curl -X POST http://localhost:8000/api/v1/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"username": "admin", "password": "admin123"}'

# Response includes access_token, refresh_token, and user info

# 2. Use token for authenticated requests
curl -X GET http://localhost:8000/api/v1/auth/me \\
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# 3. Refresh token
curl -X POST http://localhost:8000/api/v1/auth/refresh \\
  -H "Content-Type: application/json" \\
  -d '{"refresh_token": "YOUR_REFRESH_TOKEN"}'
```

### Key Endpoints

| Endpoint | Method | Description | Auth Required |
|----------|--------|-------------|---------------|
| `/api/v1/auth/login` | POST | User authentication | No |
| `/api/v1/auth/refresh` | POST | Refresh access token | No |
| `/api/v1/auth/logout` | POST | Logout user | Yes |
| `/api/v1/auth/me` | GET | Current user info | Yes |
| `/api/v1/users` | GET/POST | User management | Yes (admin) |
| `/api/v1/agents` | GET/POST | Agent operations | Yes |
| `/api/v1/goals` | GET/POST | Goal management | Yes |
| `/api/v1/api-tokens` | GET/POST | API token management | Yes |
| `/api/v1/system/health` | GET | System health | No |
| `/api/v1/system/info` | GET | System information | Yes (admin) |

### Web Interface Features

- **Interactive Documentation**: Try endpoints directly in browser
- **Real-time Monitoring**: System health and performance metrics
- **User Management**: Create and manage users with role assignments
- **Agent Monitoring**: View agent status and performance
- **Security Audit**: Review security events and access logs

## 🐳 Deployment

### Docker Deployment

```bash
# Using the clean project (recommended)
cd clean_project

# Build and run with Docker
docker build -f config/Dockerfile -t agent-system .
docker run -p 8000:8000 --env-file .env agent-system

# Or using docker-compose
docker-compose -f config/docker-compose.yml up -d
```

### Production Deployment

```bash
# Using a production WSGI server
pip install gunicorn
gunicorn agent_system.fastapi_app:app \\
  --bind 0.0.0.0:8000 \\
  --workers 4 \\
  --timeout 120 \\
  --access-logfile - \\
  --error-logfile -
```

### Health Checks

The system provides multiple health check endpoints:

- **Basic Health**: `GET /health` - Basic system status
- **Detailed Health**: `GET /api/v1/system/health` - Detailed system information
- **Database Health**: Included in detailed health checks

## 🧪 Testing

### Test Suite

The project includes comprehensive testing:

```bash
# Run all tests
make test

# Run specific test categories
pytest tests/test_e2e_workflow.py -v
pytest tests/test_tools.py -v

# Development tests (main directory)
pytest test_comprehensive_auth.py -v
pytest test_api_documentation.py -v
pytest test_integration.py -v
```

### Test Coverage

- **Authentication System**: JWT, session management, security
- **API Endpoints**: All CRUD operations with error handling
- **Database Operations**: Model validation and transactions
- **Integration Tests**: End-to-end workflows
- **Performance Tests**: Load testing and benchmarks

## 📊 Performance

### Performance Metrics

- **Authentication**: <10ms average response time
- **API Endpoints**: Sub-50ms for most operations
- **Database Queries**: Optimized with proper indexing
- **Memory Usage**: Efficient for long-running sessions
- **Scalability**: Supports horizontal scaling

### Monitoring Features

- **Real-time Metrics**: Response times, throughput, errors
- **Health Dashboard**: System status and performance
- **Audit Logging**: Security events and access patterns
- **Performance Alerts**: Automated issue detection

## 🤝 Contributing

### Development Workflow

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Make** your changes
4. **Add** tests for new features
5. **Run** the test suite (`make test`)
6. **Commit** your changes (`git commit -m 'Add amazing feature'`)
7. **Push** to the branch (`git push origin feature/amazing-feature`)
8. **Open** a Pull Request

### Code Standards

- **Linting**: Follow PEP 8 standards (`make lint`)
- **Formatting**: Use `make format` for consistent formatting
- **Type Checking**: Ensure type hints are complete (`make typecheck`)
- **Testing**: Maintain high test coverage (`make cov`)
- **Documentation**: Update docs for new features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](clean_project/LICENSE) file for details.

## 🆘 Support

### Documentation

- **📚 API Documentation**: http://localhost:8000/docs (when running)
- **📖 User Guide**: See `clean_project/docs/` directory
- **🏗️ Enterprise Scaling Roadmap**: `clean_project/docs/ENTERPRISE_SCALING_ROADMAP.md`
- **🔧 Configuration Guide**: See Configuration section above
- **🧪 Testing Guide**: See Testing section above

### Getting Help

- **🐛 Bug Reports**: Create GitHub issues for bugs
- **💡 Feature Requests**: Submit feature proposals
- **❓ Questions**: Use GitHub discussions
- **📧 Contact**: See project maintainers

### Common Issues

**Database Issues**:
```bash
# Reset database
rm agent_enterprise.db
python -c "from agent_system.auth_service import auth_service; from agent_system.auth_models import db_manager; db_manager.initialize(); auth_service.initialize()"
```

**Authentication Issues**:
```bash
# Reset admin user
python -c "from agent_system.auth_service import auth_service; auth_service._ensure_default_admin(auth_service.db.get_session())"
```

**Performance Issues**:
```bash
# Check system health
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/system/health
```

## 🏆 Project Status

### ✅ Completed Features

- [x] **AI Intelligence**: Autonomous reasoning and planning
- [x] **Cross-Session Learning**: Persistent knowledge
- [x] **Enterprise Authentication**: JWT with RBAC
- [x] **Web Interface**: FastAPI with interactive docs
- [x] **Tool System**: Real and mock tool support
- [x] **Security Features**: Rate limiting, audit logging
- [x] **API Documentation**: Comprehensive OpenAPI schemas
- [x] **Testing Suite**: 100+ tests with coverage
- [x] **Performance Monitoring**: Real-time metrics
- [x] **Docker Support**: Production deployment ready

### 🔄 Next Development Phase

- [ ] **Database Migrations**: Alembic workflow documentation
- [ ] **Performance Monitoring**: Prometheus/Grafana integration
- [ ] **Security Hardening**: Enhanced secrets management
- [ ] **Plugin Ecosystem**: Documentation and templates
- [ ] **Load Testing**: Comprehensive performance testing
- [ ] **Cloud Deployment**: AWS/Azure/GCP deployment guides

---

<div align="center">

**🤖 Built with ❤️ for autonomous AI agent development**

[⭐ Star this repo](https://github.com/your-repo) • [📖 Read the docs](clean_project/docs/) • [🐛 Report issues](https://github.com/your-repo/issues)

</div>
