#!/usr/bin/env k6
/**
 * Load Test Configuration and Utilities
 * Shared configuration and helper functions for all load tests
 */

// Base URLs and endpoints
export const BASE_URL = __ENV.API_BASE_URL || 'http://localhost:8000';
export const WS_BASE_URL = __ENV.WS_BASE_URL || 'ws://localhost:8000/ws';
export const TEST_ENV = __ENV.TEST_ENV || 'development';

// Test configuration
export const TEST_CONFIG = {
  // Request limits
  REQUEST_TIMEOUT: 30000, // 30 seconds
  CONNECT_TIMEOUT: 10000, // 10 seconds

  // Performance thresholds
  PERFORMANCE_THRESHOLDS: {
    HEALTH_CHECK_MAX_TIME: 500,    // ms
    API_ENDPOINT_MAX_TIME: 2000,   // ms
    CREATE_OPERATION_MAX_TIME: 5000, // ms
    STRESS_TEST_MAX_TIME: 3000,    // ms
  },

  // Rate limiting
  DEFAULT_RATE_LIMIT: {
    requests_per_minute: 1000,
    burst_size: 100,
  },

  // Test data
  DEFAULT_USER: {
    username: 'loadtest_user',
    email: 'loadtest@example.com',
    password: 'SecurePassword123!',
  },

  // Endpoints
  ENDPOINTS: {
    HEALTH: '/health',
    SYSTEM_INFO: '/api/v1/system/info',
    AGENTS: '/api/v1/agents',
    AGENTS_CREATE: '/api/v1/agents',
    AGENTS_GOALS: '/api/v1/agents/goals',
    GOALS_CREATE: '/api/v1/goals',
    MONITORING: '/metrics',
    DOCS: '/docs',
  },

  // WebSocket endpoints
  WS_ENDPOINTS: {
    AGENT_WS: '/ws',
    NOTIFICATIONS: '/ws/notifications',
  },
};

// Load test scenarios
export const SCENARIOS = {
  // Quick validation (30 seconds)
  SMOKE: {
    vus: 1,
    duration: '30s',
    description: 'Basic functionality validation',
    weight: 1,
  },

  // Normal load (10 minutes)
  LOAD: {
    stages: [
      { duration: '1m', target: 5, description: 'Warmup' },
      { duration: '5m', target: 5, description: 'Normal load' },
      { duration: '2m', target: 10, description: 'Increased load' },
      { duration: '2m', target: 0, description: 'Cooldown' },
    ],
    description: 'Normal expected production load',
    weight: 5,
  },

  // Stress testing (15 minutes)
  STRESS: {
    stages: [
      { duration: '2m', target: 10, description: 'Ramp up' },
      { duration: '5m', target: 10, description: 'Sustained load' },
      { duration: '2m', target: 25, description: 'High load' },
      { duration: '3m', target: 25, description: 'Peak load' },
      { duration: '1m', target: 0, description: 'Cooldown' },
    ],
    description: 'Beyond normal capacity testing',
    weight: 2,
  },

  // Spike testing (5 minutes)
  SPIKE: {
    stages: [
      { duration: '30s', target: 5, description: 'Baseline' },
      { duration: '1m', target: 5, description: 'Stable' },
      { duration: '30s', target: 50, description: 'Spike start' },
      { duration: '1m', target: 50, description: 'Sustained spike' },
      { duration: '30s', target: 5, description: 'Recovery' },
      { duration: '1m', target: 5, description: 'Post spike' },
    ],
    description: 'Sudden load increase testing',
    weight: 1,
  },

  // Endurance testing (30 minutes)
  ENDURANCE: {
    stages: [
      { duration: '2m', target: 2, description: 'Startup' },
      { duration: '25m', target: 2, description: 'Long duration test' },
      { duration: '3m', target: 0, description: 'Shutdown' },
    ],
    description: 'Long duration stability test',
    weight: 1,
  },
};

// Helper functions
export function generateTestData() {
  const timestamp = Date.now();
  const random = Math.random().toString(36).substr(2, 9);

  return {
    goal: {
      title: `Load Test Goal ${timestamp}`,
      description: `Automated load test goal ${random}`,
      priority: ['low', 'normal', 'high', 'critical'][Math.floor(Math.random() * 4)],
    },
    agent: {
      name: `Load Test Agent ${timestamp}`,
      description: `Load test agent ${random}`,
      goal: `Test goal for ${random}`,
    },
    user: {
      username: `loadtest_${timestamp}`,
      email: `loadtest_${timestamp}@example.com`,
      first_name: 'Load',
      last_name: 'Test',
    },
  };
}

export function createHeaders(contentType = 'application/json', auth = null) {
  const headers = {
    'Content-Type': contentType,
    'User-Agent': 'k6-load-test/1.0',
  };

  if (auth) {
    headers['Authorization'] = `Bearer ${auth}`;
  }

  return headers;
}

export function validateResponse(response, checks, maxTime = 2000) {
  const timing = response.timings.duration;
  const statusValid = response.status >= 200 && response.status < 300;
  const timeValid = timing <= maxTime;

  const result = {
    success: statusValid && timeValid,
    status: response.status,
    timing: timing,
    maxAllowed: maxTime,
    checks: {},
  };

  // Run custom checks
  Object.entries(checks).forEach(([name, checkFn]) => {
    try {
      result.checks[name] = checkFn(response);
    } catch (error) {
      result.checks[name] = false;
      console.error(`Check '${name}' failed:`, error);
    }
  });

  return result;
}

export function logTestResult(testName, result) {
  const status = result.success ? 'PASS' : 'FAIL';
  const emoji = result.success ? '✅' : '❌';

  console.log(`${emoji} ${testName}: ${status}`);
  console.log(`   Status: ${result.status} (expected: 2xx)`);
  console.log(`   Timing: ${result.timing.toFixed(2)}ms (max: ${result.maxAllowed}ms)`);

  if (Object.keys(result.checks).length > 0) {
    console.log('   Checks:');
    Object.entries(result.checks).forEach(([name, passed]) => {
      console.log(`     ${passed ? '✅' : '❌'} ${name}`);
    });
  }
}

export function sleepRandom(min = 1, max = 5) {
  const delay = Math.random() * (max - min) + min;
  sleep(delay);
}

export function exponentialBackoffRetry(fn, maxRetries = 3, baseDelay = 1000) {
  return function(...args) {
    let lastError;

    for (let i = 0; i < maxRetries; i++) {
      try {
        return fn(...args);
      } catch (error) {
        lastError = error;
        if (i < maxRetries - 1) {
          const delay = baseDelay * Math.pow(2, i);
          console.log(`Retry ${i + 1}/${maxRetries} after ${delay}ms delay`);
          sleep(delay / 1000);
        }
      }
    }

    throw lastError;
  };
}

// Test execution helpers
export async function healthCheck() {
  const response = http.get(`${BASE_URL}${TEST_CONFIG.ENDPOINTS.HEALTH}`);
  return validateResponse(response, {
    'status is 200': (r) => r.status === 200,
    'response is JSON': (r) => {
      try {
        JSON.parse(r.body);
        return true;
      } catch {
        return false;
      }
    },
  }, TEST_CONFIG.PERFORMANCE_THRESHOLDS.HEALTH_CHECK_MAX_TIME);
}

export async function getAgents() {
  const response = http.get(`${BASE_URL}${TEST_CONFIG.ENDPOINTS.AGENTS}`);
  return validateResponse(response, {
    'status is 200': (r) => r.status === 200,
    'response contains data': (r) => r.body && r.body.length > 0,
  }, TEST_CONFIG.PERFORMANCE_THRESHOLDS.API_ENDPOINT_MAX_TIME);
}

export async function createGoal(goalData) {
  const response = http.post(
    `${BASE_URL}${TEST_CONFIG.ENDPOINTS.GOALS_CREATE}`,
    JSON.stringify(goalData),
    { headers: createHeaders() }
  );

  return validateResponse(response, {
    'status is 201 or 200': (r) => r.status === 201 || r.status === 200,
    'response has ID': (r) => {
      try {
        const data = JSON.parse(r.body);
        return data.id !== undefined;
      } catch {
        return false;
      }
    },
  }, TEST_CONFIG.PERFORMANCE_THRESHOLDS.CREATE_OPERATION_MAX_TIME);
}

// Metrics and monitoring
export function getCurrentMetrics() {
  return {
    vus: __VU,
    iterations: __ITER,
    test_type: __ENV.TEST_TYPE || 'custom',
    timestamp: new Date().toISOString(),
  };
}

export function recordCustomMetric(name, value, tags = {}) {
  // This would integrate with custom metrics system
  // For now, just log to console
  console.log(`Metric: ${name}=${value} tags=${JSON.stringify(tags)}`);
}

// Setup and teardown helpers
export function setupTest(testType) {
  console.log(`🚀 Starting ${testType} load test`);
  console.log(`📊 Base URL: ${BASE_URL}`);
  console.log(`🔧 Environment: ${TEST_ENV}`);

  return {
    startTime: Date.now(),
    testType,
    config: TEST_CONFIG,
  };
}

export function teardownTest(testContext) {
  const duration = Date.now() - testContext.startTime;
  console.log(`🏁 Completed ${testContext.testType} test (${duration}ms)`);
  console.log(`📈 VUs: ${__VU}, Iterations: ${__ITER}`);
}