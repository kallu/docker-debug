# Docker Debug Container

A Docker container designed to simulate common failure scenarios in ECS/EKS environments for debugging and testing purposes.

## Available Endpoints

### `GET /`
Returns a list of all available endpoints and their descriptions.

### `GET /healthy`
**Purpose**: Simulates a healthy service
**Response**: 200 OK
**Use Case**: Test successful health checks

```bash
curl http://localhost:8080/healthy
```

### `GET /unhealthy`
**Purpose**: Simulates an unhealthy service
**Response**: 500 Internal Server Error
**Use Case**: Test health check failures and container restarts

```bash
curl http://localhost:8080/unhealthy
```

### `GET /slow-start`
**Purpose**: Simulates slow application startup
**Response**: 200 OK after 60 seconds
**Use Case**: Test health check initial delay settings and startup probes

```bash
curl http://localhost:8080/slow-start
```

### `GET /memory-leak`
**Purpose**: Allocates ~100MB of memory on each call
**Response**: 200 OK with total allocated memory
**Use Case**: Test OOMKilled scenarios and memory limits

```bash
# Call multiple times to trigger OOM
curl http://localhost:8080/memory-leak
```

## Building the Container

```bash
docker build -t docker-debug:latest .
```

## Running the Container

### Basic run
```bash
docker run -p 8080:8080 -e THIS_IS_IMPORTANT=value docker-debug:latest
```

**Note:** The `THIS_IS_IMPORTANT` environment variable is required. The container will fail to start without it.

### Run with memory limit (useful for testing memory-leak)
```bash
docker run -p 8080:8080 -m 512m -e THIS_IS_IMPORTANT=value docker-debug:latest
```

### Run with custom port
```bash
docker run -p 3000:3000 -e PORT=3000 -e THIS_IS_IMPORTANT=value docker-debug:latest
```

## Testing Scenarios

### Test Health Check Failure
Configure your ECS/EKS health check to use `/healthy`, then switch to `/unhealthy` to trigger failures.

### Test Slow Startup
1. Set health check path to `/slow-start`
2. Configure initial delay shorter than 60s
3. Watch the container fail health checks and restart

### Test Memory Limits
1. Run container with memory limit: `docker run -p 8080:8080 -m 256m docker-debug:latest`
2. Call `/memory-leak` endpoint 3-4 times
3. Container will be OOMKilled

```bash
# Trigger memory leak multiple times
for i in {1..5}; do curl http://localhost:8080/memory-leak; sleep 1; done
```

### Test Missing Environment Variable
The application requires the `THIS_IS_IMPORTANT` environment variable to be set. If it's missing, the container will fail to start.

**Test locally:**
```bash
# Without the variable - container fails
docker run -p 8080:8080 docker-debug:latest

# With the variable - container starts
docker run -p 8080:8080 -e THIS_IS_IMPORTANT=value docker-debug:latest
```

**Test in ECS:**
Remove or comment out the `THIS_IS_IMPORTANT` environment variable from the task definition to simulate a misconfiguration scenario. The task will fail immediately with a `KeyError`.

## Deploying to ECS

### ECS Service with Circuit Breaker (Prevents Infinite Restarts)

When running as an ECS Service (not a standalone Task), you can use the **Deployment Circuit Breaker** to prevent endless restart loops. After N failed attempts, ECS will stop trying to deploy and optionally roll back.

**Key Settings:**
- `deploymentCircuitBreaker.enable: true` - Stops deployment after repeated failures
- `deploymentCircuitBreaker.rollback: true` - Automatically reverts to last working version
- `healthCheckGracePeriodSeconds: 60` - Time before load balancer health checks start counting

See `ecs-task-definition.json` and `ecs-service-definition.json` for complete examples.

### Creating the Service

```bash
# Register task definition
aws ecs register-task-definition --cli-input-json file://ecs-task-definition.json

# Create service with circuit breaker
aws ecs create-service --cli-input-json file://ecs-service-definition.json
```

### Testing Circuit Breaker Behavior

**Scenario 1: Unhealthy Container**
```bash
# Change health check to point to /unhealthy endpoint in task definition
# Deploy the service - circuit breaker will trigger after ~10 minutes of failures
# Service will stop attempting deployment and rollback if enabled
```

**Scenario 2: Slow Startup Timeout**
```bash
# Set health check path to /slow-start (takes 60s)
# Set startPeriod to 30s (shorter than response time)
# Circuit breaker will detect pattern and stop deployment
```

### ECS Task Definition (Full Example)

See `ecs-task-definition.json` for the complete configuration including:
- Health check with proper `startPeriod` for slow starts
- CloudWatch Logs configuration
- Memory and CPU allocation
- Fargate compatibility

### Health Check Parameters Explained

```json
"healthCheck": {
  "command": ["CMD-SHELL", "curl -f http://localhost:8080/healthy || exit 1"],
  "interval": 30,        // Check every 30 seconds
  "timeout": 5,          // Fail if check takes > 5 seconds
  "retries": 3,          // Mark unhealthy after 3 consecutive failures
  "startPeriod": 60      // Grace period for slow startup (failures don't count)
}
```

**For this debug container:**
- Use `startPeriod: 60` or higher when testing `/slow-start` endpoint
- Use `startPeriod: 10` when testing normal `/healthy` endpoint
- Set `retries: 3` to see container restart after 3 failed checks

### Without Circuit Breaker (Default Behavior)

If you don't enable the circuit breaker, ECS will continuously try to restart failed tasks indefinitely. This is useful for transient failures but problematic for persistent issues like misconfiguration.

## Kubernetes Deployment Example

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: debug-container
spec:
  replicas: 1
  selector:
    matchLabels:
      app: debug
  template:
    metadata:
      labels:
        app: debug
    spec:
      containers:
      - name: debug-app
        image: docker-debug:latest
        ports:
        - containerPort: 8080
        env:
        - name: THIS_IS_IMPORTANT
          value: "configured"
        resources:
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /healthy
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /healthy
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 5
```

## Logs

All endpoints log their activity to stdout for CloudWatch/container logs monitoring:

```
2024-01-15 10:30:45 - __main__ - INFO - Starting debug container on port 8080
2024-01-15 10:31:12 - __main__ - INFO - Health check: healthy
2024-01-15 10:31:45 - __main__ - ERROR - Health check: unhealthy - returning 500
2024-01-15 10:32:10 - __main__ - WARNING - Memory leak triggered - total allocated: 300 MB
```
