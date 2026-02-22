#!/usr/bin/env python3
import os
import time
from flask import Flask, jsonify
import logging

app = Flask(__name__)

# Configure logging to stdout
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global variable to hold allocated memory for memory leak
memory_hog = []

@app.route('/')
def index():
    """Root endpoint with available routes"""
    return jsonify({
        'message': 'Docker Debug Container',
        'endpoints': {
            '/healthy': 'Returns 200 OK - simulates healthy service',
            '/unhealthy': 'Returns 500 error - simulates unhealthy service',
            '/memory-leak': 'Allocates memory continuously - simulates memory leak',
            '/status': 'Forwards internally to configured scenario URL (set via STATUS_ENDPOINT env var)'
        },
        'environment_variables': {
            'STATUS_ENDPOINT': 'Set which endpoint /status forwards to (default: /healthy)',
            'SLOW_START_DELAY': 'Delay in seconds before app becomes ready (simulates slow startup)',
            'PORT': 'Port to run on (default: 8080)'
        }
    })

@app.route('/status')
def status():
    """Status endpoint that internally forwards to configured scenario"""
    status_endpoint = os.getenv('STATUS_ENDPOINT', '/healthy')
    logger.info(f"Status endpoint forwarding internally to: {status_endpoint}")

    # Map endpoint paths to their handler functions
    endpoint_handlers = {
        '/healthy': healthy,
        '/unhealthy': unhealthy,
        '/memory-leak': memory_leak
    }

    # Get the handler function and call it directly
    handler = endpoint_handlers.get(status_endpoint)
    if handler:
        return handler()
    else:
        # Default to healthy if unknown endpoint
        logger.warning(f"Unknown status endpoint: {status_endpoint}, defaulting to healthy")
        return healthy()

@app.route('/healthy')
def healthy():
    """Healthy endpoint - returns 200 OK"""
    logger.info("Health check: healthy")
    return jsonify({
        'status': 'healthy',
        'message': 'Service is running normally'
    }), 200

@app.route('/unhealthy')
def unhealthy():
    """Unhealthy endpoint - returns 500 error"""
    logger.error("Health check: unhealthy - returning 500")
    return jsonify({
        'status': 'unhealthy',
        'message': 'Service is experiencing issues'
    }), 500

@app.route('/memory-leak')
def memory_leak():
    """Memory leak endpoint - allocates ~100MB each call"""
    global memory_hog

    # Allocate approximately 100MB of memory
    chunk_size = 100 * 1024 * 1024  # 100 MB
    memory_chunk = 'x' * chunk_size
    memory_hog.append(memory_chunk)

    total_mb = len(memory_hog) * 100
    logger.warning(f"Memory leak triggered - total allocated: {total_mb} MB")

    return jsonify({
        'status': 'leaked',
        'message': f'Allocated another 100MB',
        'total_allocated_mb': total_mb,
        'warning': 'Memory will continue to grow until OOMKilled'
    }), 200

if __name__ == '__main__':
    important_value = os.environ['THIS_IS_IMPORTANT']
    port = int(os.getenv('PORT', 8080))

    # Simulate slow startup if configured
    slow_start_delay = int(os.getenv('SLOW_START_DELAY', 0))
    if slow_start_delay > 0:
        logger.info(f"SLOW_START_DELAY set to {slow_start_delay} seconds - simulating slow startup")
        time.sleep(slow_start_delay)
        logger.info(f"Startup delay complete - container is now ready")

    logger.info(f"Starting debug container on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
