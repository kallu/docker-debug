#!/bin/bash
# Script to deploy the debug container to ECS

set -e

# Configuration - Update these values
AWS_REGION="us-east-1"
AWS_ACCOUNT_ID="123456789012"
ECR_REPO_NAME="docker-debug"
CLUSTER_NAME="your-cluster-name"
SERVICE_NAME="docker-debug-service"

echo "Building Docker image..."
docker build -t ${ECR_REPO_NAME}:latest .

echo "Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | \
  docker login --username AWS --password-stdin ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com

echo "Creating ECR repository if it doesn't exist..."
aws ecr describe-repositories --repository-names ${ECR_REPO_NAME} --region ${AWS_REGION} 2>/dev/null || \
  aws ecr create-repository --repository-name ${ECR_REPO_NAME} --region ${AWS_REGION}

echo "Tagging and pushing image to ECR..."
docker tag ${ECR_REPO_NAME}:latest ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest
docker push ${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO_NAME}:latest

echo "Registering task definition..."
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.json \
  --region ${AWS_REGION}

echo "Creating or updating ECS service..."
# Check if service exists
if aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --region ${AWS_REGION} | grep -q "ACTIVE"; then
  echo "Service exists, updating..."
  aws ecs update-service \
    --cluster ${CLUSTER_NAME} \
    --service ${SERVICE_NAME} \
    --task-definition docker-debug-app \
    --force-new-deployment \
    --region ${AWS_REGION}
else
  echo "Service does not exist, creating..."
  aws ecs create-service \
    --cli-input-json file://ecs-service-definition.json \
    --region ${AWS_REGION}
fi

echo "Deployment complete! Monitor with:"
echo "aws ecs describe-services --cluster ${CLUSTER_NAME} --services ${SERVICE_NAME} --region ${AWS_REGION}"
