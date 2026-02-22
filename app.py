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
            '/slow-start': 'Takes 60s to respond - simulates slow startup',
            '/memory-leak': 'Allocates memory continuously - simulates memory leak'
        }
    })

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

@app.route('/slow-start')
def slow_start():
    """Slow startup endpoint - takes 60s to respond"""
    logger.info("Slow start endpoint called - will take 60 seconds")
    time.sleep(60)
    logger.info("Slow start endpoint responding after 60 seconds")
    return jsonify({
        'status': 'ready',
        'message': 'Service ready after 60 seconds',
        'delay_seconds': 60
    }), 200

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
    logger.info(f"Starting debug container on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)
