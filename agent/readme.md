# FaaS Dynamic Scheduler

A **tail-latency aware**, **multi-architecture** Function-as-a-Service (FaaS) scheduler that intelligently adapts between centralized, federated, and decentralized architectures based on real-time performance metrics.

## 🚀 Features

### **Intelligent Architecture Selection**
- **Dynamic Switching**: Automatically selects optimal architecture based on tail latency (P95/P50 ratios)
- **Multi-Architecture Support**: Centralized, Federated, Decentralized, and Dynamic modes
- **Performance-Aware**: Uses historical execution data to make informed scheduling decisions

### **Advanced Scheduling Algorithms**
- **Weighted Target Selection**: Probabilistic node selection based on response time history
- **Load-Aware Offloading**: Considers CPU load and hop count for intelligent task distribution
- **Zone-Aware Routing**: Optimizes scheduling within and across geographical zones

### **Real-Time Monitoring**
- **System Metrics**: CPU usage, load averages, memory utilization
- **Performance Tracking**: Response times, execution durations, QPS monitoring
- **Tail Latency Analysis**: P95/P50 ratio tracking for performance optimization

### **Distributed Coordination**
- **Multi-Node Architecture**: Supports cloud controllers and edge controllers
- **Cross-Zone Communication**: Seamless task offloading between zones
- **Fault Tolerance**: Graceful fallback mechanisms for network failures

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Centralized   │    │   Federated     │    │ Decentralized   │
│                 │    │                 │    │                 │
│ Cloud Controller│    │ Edge Controllers│    │ Peer-to-Peer    │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │   Scheduler │ │    │ │Zone Schedulr│ │    │ │Local Schedulr│ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
│        │        │    │        │        │    │        │        │
│        ▼        │    │        ▼        │    │        ▼        │
│ ┌─────────────┐ │    │ ┌─────────────┐ │    │ ┌─────────────┐ │
│ │FaaS Executor│ │    │ │FaaS Executor│ │    │ │FaaS Executor│ │
│ └─────────────┘ │    │ └─────────────┘ │    │ └─────────────┘ │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📁 Project Structure

```
faas-scheduler/
├── main.py                     # Application entry point
├── api/
│   └── routes.py              # HTTP API endpoints
├── core/
│   ├── scheduler_service.py    # Main scheduling orchestration
│   ├── execution_engine.py     # Function execution engine
│   ├── target_selector.py      # Node selection algorithms
│   ├── tail_scheduler.py       # Dynamic architecture selection
│   ├── config_manager.py       # Configuration management
│   └── metrics_collector.py    # Performance monitoring
├── arch/
│   └── architecture.yaml       # System configuration
└── requirements.txt            # Python dependencies
```

## 🛠️ Installation

### Prerequisites
- Python 3.8+
- pip package manager
- Access to FaaS platform (OpenFaaS, Knative, etc.)

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Configuration
Create your `arch/architecture.yaml`:

```yaml
architecture: "dynamic"  # centralized, federated, decentralized, dynamic
node:
  id: "node-1"
topology:
  - id: "cloud-controller-1"
    address: "10.0.1.100"
    role: "cloud-controller"
    zone: "us-west-1"
  - id: "edge-controller-1"
    address: "10.0.2.100"
    role: "edge-controller"
    zone: "us-west-1"
  - id: "edge-node-1"
    address: "10.0.2.101"
    role: "worker"
    zone: "us-west-1"
```

## 🚀 Usage

### Start the Scheduler
```bash
python main.py --config arch/architecture.yaml
```

### API Endpoints

#### Execute Function
```bash
curl -X POST http://localhost:31113/entry \
  -H "Content-Type: application/json" \
  -d '{
    "fn_name": "hello-world",
    "payload": "Hello FaaS!",
    "arch": "dynamic"
  }'
```

#### Get System Metrics
```bash
curl http://localhost:31113/load
```

#### Architecture Performance Metrics
```bash
curl http://localhost:31113/arch_metrics
```

#### Change Architecture
```bash
curl -X POST http://localhost:31113/reload \
  -H "Content-Type: application/json" \
  -d '{"architecture": "federated"}'
```

## 📊 Monitoring & Metrics

### Performance Metrics
- **Response Time**: Average and P95 response times per node
- **Tail Latency Ratio**: P95/P50 ratio for architecture selection
- **QPS Tracking**: Queries per second monitoring
- **Architecture Ratios**: Dynamic weight distribution across architectures

### System Metrics
- **CPU Usage**: Real-time CPU utilization
- **Load Average**: 1, 5, and 15-minute load averages
- **Memory Usage**: Available memory and utilization
- **Network Latency**: Inter-node communication delays

## 🔧 Configuration

### Architecture Modes

#### Centralized
- Single cloud controller manages all scheduling
- Optimal for consistent workloads with predictable patterns
- Best performance for low-latency requirements

#### Federated
- Edge controllers manage local zones
- Balances locality with coordination
- Ideal for geographically distributed deployments

#### Decentralized
- Peer-to-peer scheduling decisions
- Maximum resilience and fault tolerance
- Best for highly variable workloads

#### Dynamic
- Automatically switches between architectures
- Uses tail latency metrics to optimize performance
- Recommended for production deployments

### Tuning Parameters

```yaml
# Tail Scheduler Configuration
tail_scheduler:
  soft_d2f_threshold: 1.5    # Soft threshold for decentralized→federated
  hard_d2f_threshold: 2.5    # Hard threshold for decentralized→federated
  soft_f2c_threshold: 1.7    # Soft threshold for federated→centralized
  hard_f2c_threshold: 2.7    # Hard threshold for federated→centralized
  min_samples: 10            # Minimum samples for ratio calculation
  sample_interval: 2         # Sampling interval in seconds
```

## 🧪 Testing

### Unit Tests
```bash
python -m pytest tests/unit/
```

### Integration Tests
```bash
python -m pytest tests/integration/
```

### Load Testing
```bash
# Install artillery for load testing
npm install -g artillery

# Run load test
artillery run tests/load/basic-load.yml
```

## 📈 Performance Optimization

### Tail Latency Optimization
The scheduler continuously monitors P95/P50 latency ratios:
- **Ratio < 1.5**: Remains in current architecture
- **1.5 ≤ Ratio < 2.5**: Gradual transition to more centralized architecture
- **Ratio ≥ 2.5**: Immediate transition to centralized architecture

### Load Balancing
- **Weighted Selection**: Nodes with better performance history receive more requests
- **Zone Affinity**: Prefers local zone execution to minimize network overhead
- **Adaptive Offloading**: Considers hop count and system load for offloading decisions

## 🐛 Troubleshooting

### Common Issues

#### High Tail Latency
```bash
# Check current architecture ratios
curl http://localhost:31113/arch_metrics

# Adjust thresholds if needed
curl -X POST http://localhost:31113/update_threshold \
  -d '{"soft_d2f": 1.2, "hard_d2f": 2.0}'
```

#### Node Communication Failures
```bash
# Check node connectivity
curl http://localhost:31113/configuration

# Verify network connectivity between nodes
ping <node-address>
```

#### Performance Degradation
```bash
# Monitor system load
curl http://localhost:31113/load

# Check recent execution durations
curl http://localhost:31113/durations
```

### Development Setup
```bash
# Install development dependencies
pip install -r requirements-dev.txt

# Run pre-commit hooks
pre-commit install

# Run tests with coverage
pytest --cov=core tests/
```
## 📧 Contact

For questions, issues, or contributions:
- Create an issue in the GitHub repository
- Email: [yitao.lei@student.uva.nl]

**Happy Scheduling! 🎯**