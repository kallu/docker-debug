# Docker Debug Container

A Docker container designed to simulate common failure scenarios in AWS ECS environments for debugging and testing purposes.

## Available Endpoints

### `GET /`
Returns a list of all available endpoints and their descriptions.

### `GET /status`
**Purpose**: Forwards internally to a configured error scenario endpoint
**Response**: Returns the response from the endpoint specified by `STATUS_ENDPOINT` environment variable
**Use Case**: Health check endpoint that can be configured to simulate different scenarios
**Default**: Forwards to `/healthy` if `STATUS_ENDPOINT` is not set

```bash
# Set the status endpoint via environment variable
docker run -p 8080:8080 -e STATUS_ENDPOINT=/unhealthy -e THIS_IS_IMPORTANT=value docker-debug:latest
curl http://localhost:8080/status  # Will return 500 from /unhealthy
```

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

## Environment Variables

- **`THIS_IS_IMPORTANT`** (required): Must be set or the container will fail to start with a KeyError
- **`STATUS_ENDPOINT`** (optional): Specifies which endpoint `/status` should forward to (default: `/healthy`)
  - Valid values: `/healthy`, `/unhealthy`, `/memory-leak`
- **`SLOW_START_DELAY`** (optional): Delay in seconds before the app starts accepting requests (default: 0)
  - Used to simulate slow-starting containers
- **`PORT`** (optional): Port the app listens on (default: 8080)

## Testing Scenarios

### Test Health Check Failure
Configure your ECS health check to use `/healthy`, then switch to `/unhealthy` to trigger failures.

### Test Slow Startup
The slow startup scenario uses the `SLOW_START_DELAY` environment variable to delay the container's startup by 60 seconds. During this time, the container won't respond to health checks.

```bash
# Run locally with slow startup
docker run -p 8080:8080 -e SLOW_START_DELAY=60 -e THIS_IS_IMPORTANT=value docker-debug:latest

# Container will take 60 seconds before it starts accepting requests
# Health checks will fail during this period
```

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

The CloudFormation template (`ecs-docker-debug.yaml`) includes a parameter `pErrorScenario` that automatically configures the container for different failure scenarios:

### Available Error Scenarios

1. **healthy** (default): `/status` → `/healthy`, `THIS_IS_IMPORTANT` is set
   - Service runs normally and passes health checks

2. **unhealthy**: `/status` → `/unhealthy`, `THIS_IS_IMPORTANT` is set
   - Health checks fail with 500 errors, causing container restarts

3. **slow-start**: `/status` → `/healthy`, `SLOW_START_DELAY` = 60, `THIS_IS_IMPORTANT` is set
   - Container startup is delayed by 60 seconds, testing startup probe and grace period settings

4. **memory-leak**: `/status` → `/memory-leak`, `THIS_IS_IMPORTANT` is set
   - Each health check allocates 100MB, eventually triggering OOMKilled

5. **missing-env-var**: `/status` → `/healthy`, `THIS_IS_IMPORTANT` is NOT set
   - Container fails to start due to missing required environment variable

### Example Deployment with Error Scenario

```bash
# Deploy with unhealthy scenario
aws cloudformation create-stack \
  --stack-name docker-debug-unhealthy \
  --template-body file://ecs-docker-debug.yaml \
  --parameters \
    ParameterKey=pDockerImage,ParameterValue=your-image:tag \
    ParameterKey=pVpcId,ParameterValue=vpc-xxxxx \
    ParameterKey=pPublicSubnetIds,ParameterValue="subnet-xxx,subnet-yyy" \
    ParameterKey=pPrivateSubnetIds,ParameterValue="subnet-aaa,subnet-bbb" \
    ParameterKey=pErrorScenario,ParameterValue=unhealthy

# Deploy with missing environment variable scenario
aws cloudformation create-stack \
  --stack-name docker-debug-missing-env \
  --template-body file://ecs-docker-debug.yaml \
  --parameters \
    ParameterKey=pDockerImage,ParameterValue=your-image:tag \
    ParameterKey=pVpcId,ParameterValue=vpc-xxxxx \
    ParameterKey=pPublicSubnetIds,ParameterValue="subnet-xxx,subnet-yyy" \
    ParameterKey=pPrivateSubnetIds,ParameterValue="subnet-aaa,subnet-bbb" \
    ParameterKey=pErrorScenario,ParameterValue=missing-env-var
```

### Health Check Configuration

When configuring ECS health checks for this container, consider these parameters:

**Health Check Parameters:**
- `interval`: How often to check (e.g., 30 seconds)
- `timeout`: Maximum time for check to respond (e.g., 5 seconds)
- `retries`: Consecutive failures before marking unhealthy (e.g., 3)
- `startPeriod`: Grace period for slow startup where failures don't count (e.g., 60 seconds)

**For this debug container:**
- Use `startPeriod: 60` or higher when testing the `slow-start` scenario (with `SLOW_START_DELAY=60`)
- Use `startPeriod: 10` when testing normal `/healthy` endpoint
- Set `retries: 3` to see container restart after 3 failed checks

### CloudWatch Alarms

The CloudFormation template automatically creates three CloudWatch alarms to monitor the health of your ECS service:

#### 1. Service Restart Alarm (`{StackName}-service-restarts`)
**Purpose**: Detects when the ECS service is experiencing repeated task restarts

**Triggers when:**
- Running task count falls below desired count at least 2 times within a 5-minute period
- Indicates the container is crashing and restarting repeatedly

**Use cases:**
- Detects the `unhealthy` scenario (container fails health checks)
- Detects the `missing-env-var` scenario (container crashes on startup)
- Catches any configuration issues causing container instability

**Configuration:**
- Metric: `RunningTaskCount` (ECS/ContainerInsights)
- Evaluation: 5 periods of 1 minute each
- Threshold: < 1 running task
- Datapoints to alarm: 2 out of 5

#### 2. Zero Running Tasks Alarm (`{StackName}-zero-running-tasks`)
**Purpose**: Alerts when the service has no running tasks at all

**Triggers when:**
- No tasks are running for 1 minute
- More critical than the restart alarm - indicates complete service outage

**Use cases:**
- Service cannot start any tasks successfully
- All tasks have crashed
- Deployment circuit breaker has stopped the service

**Configuration:**
- Metric: `RunningTaskCount` (ECS/ContainerInsights)
- Evaluation: 1 period of 1 minute
- Threshold: < 1 running task
- Missing data: Treated as breaching (alarm state)

#### 3. Zero Healthy Targets Alarm (`{StackName}-zero-healthy-targets`)
**Purpose**: Alerts when the ALB has no healthy targets

**Triggers when:**
- No containers are passing the ALB health checks for 1 minute
- Tasks may be running but failing health checks

**Use cases:**
- Containers are running but unhealthy (like the `unhealthy` scenario)
- Health check endpoint is unreachable
- Containers take too long to start (like the `slow-start` scenario with insufficient grace period)

**Configuration:**
- Metric: `HealthyHostCount` (AWS/ApplicationELB)
- Evaluation: 1 period of 1 minute
- Threshold: < 1 healthy target
- Missing data: Treated as breaching (alarm state)

**Note**: All three alarms are automatically created when you deploy the CloudFormation stack. They help you quickly identify which type of failure is occurring in your debug scenarios.

## Logs

All endpoints log their activity to stdout for CloudWatch/container logs monitoring:

```
2024-01-15 10:30:45 - __main__ - INFO - Starting debug container on port 8080
2024-01-15 10:31:12 - __main__ - INFO - Health check: healthy
2024-01-15 10:31:45 - __main__ - ERROR - Health check: unhealthy - returning 500
2024-01-15 10:32:10 - __main__ - WARNING - Memory leak triggered - total allocated: 300 MB
```
