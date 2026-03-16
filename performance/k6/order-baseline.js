import crypto from "k6/crypto";
import encoding from "k6/encoding";
import http from "k6/http";
import { check, fail, sleep } from "k6";

const config = {
  apiBaseUrl: (__ENV.API_BASE_URL || "http://127.0.0.1:8000/api/v1").replace(/\/$/, ""),
  username: __ENV.LOGIN_USERNAME || "demo@example.com",
  password: __ENV.LOGIN_PASSWORD || "changethis",
  callbackSecret: __ENV.PAYMENT_CALLBACK_SIGNING_SECRET || "changethis",
  paymentProvider: __ENV.PAYMENT_PROVIDER || "mockpay",
  thinkTimeMs: Number(__ENV.THINK_TIME_MS || 200),
};

export const options = {
  scenarios: {
    order_flow: {
      executor: "constant-vus",
      vus: Number(__ENV.K6_VUS || 5),
      duration: __ENV.K6_DURATION || "30s",
    },
  },
  thresholds: {
    http_req_failed: ["rate<0.05"],
    http_req_duration: ["p(95)<1200"],
  },
};

function jsonHeaders(token) {
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

function formHeaders() {
  return {
    "Content-Type": "application/x-www-form-urlencoded",
  };
}

function request(method, path, body, params = {}) {
  const url = `${config.apiBaseUrl}${path}`;
  return http.request(method, url, body, params);
}

function assertOk(response, expectedStatus, label) {
  const ok = check(response, {
    [`${label} status is ${expectedStatus}`]: (res) => res.status === expectedStatus,
  });
  if (!ok) {
    fail(`${label} failed: ${response.status} ${response.body}`);
  }
}

function sleepThinkTime() {
  if (config.thinkTimeMs > 0) {
    sleep(config.thinkTimeMs / 1000);
  }
}

function login() {
  const payload = `username=${encodeURIComponent(config.username)}&password=${encodeURIComponent(config.password)}`;
  const response = request("POST", "/login/access-token", payload, { headers: formHeaders() });
  assertOk(response, 200, "login");
  const body = response.json();
  if (!body.access_token) {
    fail(`login returned no access token: ${response.body}`);
  }
  return body.access_token;
}

function fetchMenu(token) {
  const response = request("GET", "/menu/dishes-with-skus?is_active=true&limit=100", null, {
    headers: { Authorization: `Bearer ${token}` },
  });
  assertOk(response, 200, "fetch menu");
  const dishes = response.json();
  const firstDishWithSku = dishes.find((dish) => Array.isArray(dish.skus) && dish.skus.length > 0);
  if (!firstDishWithSku) {
    fail("no active dish sku found, run demo seed first");
  }
  return firstDishWithSku.skus[0];
}

function ensureAddress(token) {
  const headers = { Authorization: `Bearer ${token}` };
  const listResponse = request("GET", "/addresses/", null, { headers });
  assertOk(listResponse, 200, "list addresses");
  const addresses = listResponse.json();
  if (addresses.length > 0) {
    const defaultAddress = addresses.find((item) => item.is_default) || addresses[0];
    return defaultAddress.id;
  }

  const createPayload = JSON.stringify({
    receiver_name: "Perf Receiver",
    receiver_phone: "13800000000",
    province: "Shanghai",
    city: "Shanghai",
    district: "Pudong",
    detail: "Performance Road 1",
    is_default: true,
  });
  const createResponse = request("POST", "/addresses/", createPayload, {
    headers: jsonHeaders(token),
  });
  assertOk(createResponse, 200, "create address");
  return createResponse.json().id;
}

function clearCart(token) {
  const response = request("DELETE", "/cart/items", null, {
    headers: { Authorization: `Bearer ${token}` },
  });
  assertOk(response, 200, "clear cart");
}

function addCartItem(token, skuId) {
  const payload = JSON.stringify({
    dish_sku_id: skuId,
    quantity: 1,
  });
  const response = request("POST", "/cart/items", payload, {
    headers: jsonHeaders(token),
  });
  assertOk(response, 200, "add cart item");
}

function createOrder(token, addressId) {
  const payload = JSON.stringify({ address_id: addressId });
  const response = request("POST", "/orders/", payload, {
    headers: jsonHeaders(token),
  });
  assertOk(response, 200, "create order");
  const order = response.json();
  if (!order.id) {
    fail(`create order returned no order id: ${response.body}`);
  }
  return order;
}

function createPayment(token, orderId) {
  const payload = JSON.stringify({
    order_id: orderId,
    provider: config.paymentProvider,
  });
  const response = request("POST", "/payments/create", payload, {
    headers: jsonHeaders(token),
  });
  assertOk(response, 200, "create payment");
  const payment = response.json();
  if (!payment.out_trade_no) {
    fail(`create payment returned no out_trade_no: ${response.body}`);
  }
  return payment;
}

function buildCallbackSignature(transactionId, timestamp, payload) {
  const message = `${config.paymentProvider}:${transactionId}:${timestamp}:${payload}`;
  const digest = crypto.hmac("sha256", config.callbackSecret, message, "binary");
  return encoding.hexEncode(digest);
}

function callbackPayment(outTradeNo) {
  const payload = JSON.stringify({
    out_trade_no: outTradeNo,
    status: "success",
  });
  const timestamp = Math.floor(Date.now() / 1000);
  const transactionId = outTradeNo;
  const signature = buildCallbackSignature(transactionId, timestamp, payload);
  const body = JSON.stringify({
    provider: config.paymentProvider,
    transaction_id: transactionId,
    timestamp,
    payload,
    signature,
  });
  const response = request("POST", "/payments/callbacks", body, {
    headers: { "Content-Type": "application/json" },
  });
  assertOk(response, 200, "payment callback");
}

function fetchOrder(token, orderId) {
  const response = request("GET", `/orders/${orderId}`, null, {
    headers: { Authorization: `Bearer ${token}` },
  });
  assertOk(response, 200, "fetch order detail");
  const order = response.json();
  const ok = check(order, {
    "order paid after callback": (item) => item.status === "paid",
  });
  if (!ok) {
    fail(`order detail did not reach paid: ${response.body}`);
  }
}

export default function () {
  const token = login();
  sleepThinkTime();

  const sku = fetchMenu(token);
  const addressId = ensureAddress(token);
  sleepThinkTime();

  clearCart(token);
  addCartItem(token, sku.id);
  sleepThinkTime();

  const order = createOrder(token, addressId);
  const payment = createPayment(token, order.id);
  callbackPayment(payment.out_trade_no);
  fetchOrder(token, order.id);

  sleepThinkTime();
}
