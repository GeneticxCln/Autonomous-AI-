#!/usr/bin/env k6
/**
 * Comprehensive Load Testing Suite for Agent API
 * Tests various endpoints under different load conditions
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';
import { Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const successCount = new Counter('success_count');
const failureCount = new Counter('failure_count');

// Configuration
const BASE_URL = __ENV.API_BASE_URL || 'http://localhost:8000';

// Test scenarios
export const options = {
  scenarios: {
    // Smoke test - quick validation
    smoke: {
      executor: 'constant-vus',
      vus: 1,
      duration: '30s',
      tags: { test_type: 'smoke' },
    },
    // Load test - normal expected load
    load: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '1m', target: 10 },  // Ramp up
        { duration: '3m', target: 10 },  // Stay at 10 users
        { duration: '1m', target: 20 },  // Ramp to 20 users
        { duration: '3m', target: 20 },  // Stay at 20 users
        { duration: '1m', target: 0 },   // Ramp down
      ],
      tags: { test_type: 'load' },
    },
    // Stress test - beyond normal capacity
    stress: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '2m', target: 50 },
        { duration: '5m', target: 50 },
        { duration: '2m', target: 100 },
        { duration: '5m', target: 100 },
        { duration: '2m', target: 0 },
      ],
      tags: { test_type: 'stress' },
    },
    // Spike test - sudden load increases
    spike: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '30s', target: 5 },
        { duration: '1m', target: 5 },
        { duration: '30s', target: 100 },  // Spike to 100
        { duration: '1m', target: 100 },   // Maintain spike
        { duration: '30s', target: 5 },    // Drop back
        { duration: '2m', target: 5 },
        { duration: '30s', target: 0 },
      ],
      tags: { test_type: 'spike' },
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<1000'], // 95% of requests must complete within 1s
    http_req_failed: ['rate<0.05'],     // Error rate must be less than 5%
    errors: ['rate<0.05'],
  },
};

// Test data
const testUsers = [
  { username: 'testuser1', email: 'test1@example.com' },
  { username: 'testuser2', email: 'test2@example.com' },
  { username: 'testuser3', email: 'test3@example.com' },
];

// Helper function to generate random test data
function generateTestData() {
  return {
    goal: `Test goal ${Math.random().toString(36).substr(2, 9)}`,
    description: `Test description ${Math.random().toString(36).substr(2, 9)}`,
    priority: ['low', 'normal', 'high', 'critical'][Math.floor(Math.random() * 4)],
  };
}

// Main test function
export default function() {
  const testType = __ENV.TEST_TYPE || 'load';

  switch (testType) {
    case 'smoke':
      runSmokeTest();
      break;
    case 'load':
      runLoadTest();
      break;
    case 'stress':
      runStressTest();
      break;
    case 'spike':
      runSpikeTest();
      break;
    default:
      runLoadTest();
  }
}

// Smoke test - basic functionality validation
function runSmokeTest() {
  // Health check
  const health = http.get(`${BASE_URL}/health`);
  check(health, {
    'health check status is 200': (r) => r.status === 200,
    'health check response time < 500ms': (r) => r.timings.duration < 500,
  }) || errorRate.add(1);

  // System info
  const systemInfo = http.get(`${BASE_URL}/api/v1/system/info`);
  check(systemInfo, {
    'system info status is 200': (r) => r.status === 200,
    'system info response time < 500ms': (r) => r.timings.duration < 500,
  }) || errorRate.add(1);

  // API documentation
  const docs = http.get(`${BASE_URL}/docs`);
  check(docs, {
    'docs status is 200': (r) => r.status === 200,
  }) || errorRate.add(1);

  sleep(1);
}

// Load test - normal operation patterns
function runLoadTest() {
  const user = testUsers[Math.floor(Math.random() * testUsers.length)];
  const testData = generateTestData();

  // Test 1: Health check (every 10th request)
  if (Math.random() < 0.1) {
    const health = http.get(`${BASE_URL}/health`);
    const success = check(health, {
      'health check status is 200': (r) => r.status === 200,
      'health check response time < 1s': (r) => r.timings.duration < 1000,
    });
    if (success) {
      successCount.add(1);
    } else {
      failureCount.add(1);
      errorRate.add(1);
    }
    sleep(1);
    return;
  }

  // Test 2: Get agents list
  const agents = http.get(`${BASE_URL}/api/v1/agents`);
  const agentsSuccess = check(agents, {
    'agents list status is 200': (r) => r.status === 200,
    'agents list response time < 2s': (r) => r.timings.duration < 2000,
  });
  if (agentsSuccess) {
    successCount.add(1);
  } else {
    failureCount.add(1);
    errorRate.add(1);
  }

  // Test 3: Create goal (less frequent)
  if (Math.random() < 0.3) {
    const goalData = {
      title: testData.goal,
      description: testData.description,
      priority: testData.priority,
    };

    const createGoal = http.post(
      `${BASE_URL}/api/v1/agents/goals`,
      JSON.stringify(goalData),
      { headers: { 'Content-Type': 'application/json' } }
    );

    const goalSuccess = check(createGoal, {
      'create goal status is 201 or 200': (r) => r.status === 201 || r.status === 200,
      'create goal response time < 5s': (r) => r.timings.duration < 5000,
    });
    if (goalSuccess) {
      successCount.add(1);
    } else {
      failureCount.add(1);
      errorRate.add(1);
    }
  }

  // Test 4: System info
  const systemInfo = http.get(`${BASE_URL}/api/v1/system/info`);
  const systemSuccess = check(systemInfo, {
    'system info status is 200': (r) => r.status === 200,
    'system info response time < 1s': (r) => r.timings.duration < 1000,
  });
  if (systemSuccess) {
    successCount.add(1);
  } else {
    failureCount.add(1);
    errorRate.add(1);
  }

  sleep(Math.random() * 3 + 1); // Random sleep 1-4 seconds
}

// Stress test - high load patterns
function runStressTest() {
  const concurrentRequests = [
    () => http.get(`${BASE_URL}/health`),
    () => http.get(`${BASE_URL}/api/v1/agents`),
    () => http.get(`${BASE_URL}/api/v1/system/info`),
  ];

  // Send multiple concurrent requests
  const responses = concurrentRequests.map(req => req());

  responses.forEach((response, index) => {
    const success = check(response, {
      [`request ${index} status is 200`]: (r) => r.status === 200,
      [`request ${index} response time < 3s`]: (r) => r.timings.duration < 3000,
    });

    if (success) {
      successCount.add(1);
    } else {
      failureCount.add(1);
      errorRate.add(1);
    }
  });

  sleep(0.5); // Short sleep for stress testing
}

// Spike test - sudden load changes
function runSpikeTest() {
  // Simulate rapid-fire requests during spike
  const requests = [
    () => http.get(`${BASE_URL}/health`),
    () => http.get(`${BASE_URL}/api/v1/agents`),
    () => http.get(`${BASE_URL}/api/v1/system/info`),
    () => http.get(`${BASE_URL}/docs`),
  ];

  // Send burst of requests
  for (let i = 0; i < 5; i++) {
    const req = requests[Math.floor(Math.random() * requests.length)];
    const response = req();

    const success = check(response, {
      'spike request status is 200': (r) => r.status === 200,
      'spike request response time < 2s': (r) => r.timings.duration < 2000,
    });

    if (success) {
      successCount.add(1);
    } else {
      failureCount.add(1);
      errorRate.add(1);
    }
  }

  sleep(0.1); // Very short sleep during spike
}

// Setup function
export function setup() {
  console.log(`Starting load test against: ${BASE_URL}`);
  console.log('Test scenarios available: smoke, load, stress, spike');

  // Pre-warm the application
  const warmup = http.get(`${BASE_URL}/health`);
  if (warmup.status === 200) {
    console.log('Application is ready for testing');
  } else {
    console.log('Warning: Application may not be ready');
  }
}

// Teardown function
export function teardown(data) {
  console.log('Load test completed');
  console.log(`Success count: ${data.success_count || 0}`);
  console.log(`Failure count: ${data.failure_count || 0}`);
  console.log(`Error rate: ${(data.error_rate || 0) * 100}%`);
}

// Summary function
export function handleSummary(data) {
  const summary = {
    timestamp: new Date().toISOString(),
    test_type: __ENV.TEST_TYPE || 'load',
    base_url: BASE_URL,
    results: {
      total_requests: data.metrics.http_reqs.count,
      success_rate: (1 - data.metrics.http_req_failed.values.rate) * 100,
      avg_response_time: data.metrics.http_req_duration.values.avg,
      p95_response_time: data.metrics.http_req_duration.values['p(95)'],
      p99_response_time: data.metrics.http_req_duration.values['p(99)'],
      min_response_time: data.metrics.http_req_duration.values.min,
      max_response_time: data.metrics.http_req_duration.values.max,
      error_rate: data.metrics.http_req_failed.values.rate * 100,
      throughput: data.metrics.http_reqs.values.rate,
    },
    thresholds: {
      response_time_p95: data.metrics.http_req_duration.values['p(95)'] < 1000,
      error_rate: data.metrics.http_req_failed.values.rate < 0.05,
    },
  };

  // Save to file for CI/CD
  return {
    'load-test-results.json': JSON.stringify(summary, null, 2),
    'load-test-summary.txt': textSummary(data, { indent: ' ', enableColors: true }),
  };
}

// Helper for text summary
function textSummary(data, options = {}) {
  let text = '';
  const indent = options.indent || '  ';
  const enableColors = options.enableColors || false;

  text += 'Load Test Summary\n';
  text += '='.repeat(50) + '\n\n';

  text += `${indent}Total Requests: ${data.metrics.http_reqs.count}\n`;
  text += `${indent}Success Rate: ${((1 - data.metrics.http_req_failed.values.rate) * 100).toFixed(2)}%\n`;
  text += `${indent}Error Rate: ${(data.metrics.http_req_failed.values.rate * 100).toFixed(2)}%\n`;
  text += `${indent}Average Response Time: ${data.metrics.http_req_duration.values.avg.toFixed(2)}ms\n`;
  text += `${indent}95th Percentile: ${data.metrics.http_req_duration.values['p(95)'].toFixed(2)}ms\n`;
  text += `${indent}99th Percentile: ${data.metrics.http_req_duration.values['p(99)'].toFixed(2)}ms\n`;
  text += `${indent}Throughput: ${data.metrics.http_reqs.values.rate.toFixed(2)} req/s\n`;

  text += '\nThresholds:\n';
  text += `${indent}Response Time (p95 < 1000ms): ${data.metrics.http_req_duration.values['p(95)'] < 1000 ? 'PASS' : 'FAIL'}\n`;
  text += `${indent}Error Rate (< 5%): ${data.metrics.http_req_failed.values.rate < 0.05 ? 'PASS' : 'FAIL'}\n`;

  return text;
}