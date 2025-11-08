#!/usr/bin/env k6
/**
 * WebSocket Load Testing for Agent API
 * Tests real-time communication and WebSocket connections
 */

import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('ws_errors');
const connectionTime = new Trend('ws_connection_time');
const messageLatency = new Trend('ws_message_latency');

// Configuration
const WS_BASE_URL = __ENV.WS_BASE_URL || 'ws://localhost:8000/ws';
const API_BASE_URL = __ENV.API_BASE_URL || 'http://localhost:8000';

export const options = {
  scenarios: {
    websocket_load: {
      executor: 'ramping-vus',
      startVUs: 1,
      stages: [
        { duration: '1m', target: 5 },
        { duration: '3m', target: 5 },
        { duration: '1m', target: 10 },
        { duration: '3m', target: 10 },
        { duration: '1m', target: 0 },
      ],
      tags: { test_type: 'websocket' },
    },
  },
  thresholds: {
    ws_connect_time: ['p(95)<1000'],
    ws_message_latency: ['p(95)<500'],
    ws_errors: ['rate<0.1'],
  },
};

export default function() {
  const vus = __VU;
  const vuId = vus || Math.floor(Math.random() * 1000);

  // Test WebSocket connection and messaging
  const params = { tag: `vu_${vuId}` };

  const response = ws.connect(WS_BASE_URL, params, function(socket) {
    socket.on('open', () => {
      console.log(`WebSocket opened for VU ${vuId}`);

      // Send authentication if needed
      socket.send(JSON.stringify({
        type: 'auth',
        token: 'test-token',
        vu_id: vuId
      }));

      // Send periodic messages
      let messageCount = 0;
      const maxMessages = Math.floor(Math.random() * 10) + 5;

      const interval = setInterval(() => {
        if (messageCount >= maxMessages) {
          clearInterval(interval);
          socket.close();
          return;
        }

        const startTime = Date.now();
        const message = {
          type: 'agent_command',
          command: 'status',
          vu_id: vuId,
          message_id: messageCount,
          timestamp: new Date().toISOString()
        };

        socket.send(JSON.stringify(message));
        messageCount++;
      }, 1000 + Math.random() * 2000); // 1-3 second intervals

      // Handle incoming messages
      socket.on('message', (data) => {
        const endTime = Date.now();
        const messageData = JSON.parse(data);

        // Record message latency
        if (messageData.timestamp) {
          const latency = endTime - new Date(messageData.timestamp).getTime();
          messageLatency.add(latency);
        }

        // Check response
        const success = check(messageData, {
          'message is valid JSON': (msg) => {
            try {
              JSON.parse(msg);
              return true;
            } catch {
              return false;
            }
          },
          'message has type': (msg) => msg.type !== undefined,
        });

        if (!success) {
          errorRate.add(1);
        }
      });
    });

    socket.on('error', (e) => {
      console.log(`WebSocket error for VU ${vuId}:`, e.error());
      errorRate.add(1);
    });

    socket.on('close', () => {
      console.log(`WebSocket closed for VU ${vuId}`);
    });
  });

  // Record connection time
  connectionTime.add(response.timings.duration);
}