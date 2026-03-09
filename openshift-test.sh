#!/bin/bash
# openshift-test.sh - Verify langflow-stack deployment on OpenShift
set -euo pipefail
oc login -u admin -p ${OC_PASSWORD} https://api.ocp.8r4k4.sandbox235.opentlc.com:6443
NAMESPACE="langflow"
RHOAI_NS="redhat-ods-applications"

echo "============================================="
echo "  Langflow Stack - Deployment Verification"
echo "============================================="

# --- 1. Cluster info ---
echo ""
echo "--- Cluster Info ---"
oc version 2>/dev/null | head -4
echo "Current project: $(oc project -q)"
echo ""

# --- 2. RHOAI Operator check ---
echo "--- Red Hat OpenShift AI Operator ---"
if oc get csv -n redhat-ods-operator 2>/dev/null | grep -q rhods; then
  oc get csv -n redhat-ods-operator 2>/dev/null | grep rhods
else
  echo "WARNING: RHOAI operator not found!"
fi
echo ""

# --- 3. Llama Stack Operator check ---
echo "--- Llama Stack Operator ---"
if oc get pods -n "$RHOAI_NS" -l app.kubernetes.io/name=llama-stack-operator --no-headers 2>/dev/null | grep -q Running; then
  echo "OK: Llama Stack Operator is running"
  oc get pods -n "$RHOAI_NS" -l app.kubernetes.io/name=llama-stack-operator --no-headers 2>/dev/null
else
  echo "WARNING: Llama Stack Operator pod not found or not running"
  echo "Check: oc get pods -n $RHOAI_NS -l app.kubernetes.io/name=llama-stack-operator"
fi
echo ""

# --- 4. LlamaStackDistribution CR status ---
echo "--- LlamaStackDistribution CR ---"
if oc get llamastackdistribution -n "$NAMESPACE" 2>/dev/null | grep -q llama-stack; then
  oc get llamastackdistribution -n "$NAMESPACE" 2>/dev/null
else
  echo "WARNING: No LlamaStackDistribution CR found in $NAMESPACE"
fi
echo ""

# --- 5. All pods ---
echo "--- Pods in $NAMESPACE ---"
oc get pods -n "$NAMESPACE" --no-headers 2>/dev/null | while read -r line; do
  name=$(echo "$line" | awk '{print $1}')
  ready=$(echo "$line" | awk '{print $2}')
  status=$(echo "$line" | awk '{print $3}')
  restarts=$(echo "$line" | awk '{print $4}')
  if [ "$status" = "Running" ] && [ "$restarts" = "0" ]; then
    echo "  OK   $name ($ready) $status"
  elif [ "$status" = "Running" ]; then
    echo "  WARN $name ($ready) $status (restarts: $restarts)"
  else
    echo "  FAIL $name ($ready) $status (restarts: $restarts)"
  fi
done
echo ""

# --- 6. Services ---
echo "--- Services in $NAMESPACE ---"
oc get svc -n "$NAMESPACE" --no-headers 2>/dev/null | awk '{printf "  %-30s %s\n", $1, $5}'
echo ""

# --- 7. Routes ---
echo "--- Routes ---"
echo ""
oc get routes -n "$NAMESPACE" --no-headers 2>/dev/null | while read -r line; do
  name=$(echo "$line" | awk '{print $1}')
  host=$(echo "$line" | awk '{print $2}')
  tls=$(echo "$line" | awk '{print $5}')
  if [ -n "$tls" ] && [ "$tls" != "None" ]; then
    echo "  $name:"
    echo "    https://$host"
  else
    echo "  $name:"
    echo "    http://$host"
  fi
done
echo ""

# --- 8. LlamaStackDistribution CR check ---
echo "--- LlamaStackDistribution ---"
oc get llamastackdistribution -n "$NAMESPACE" 2>/dev/null || echo "  No LlamaStackDistribution found"
echo ""

# --- 9. Llama Stack pod logs (last 10 lines) ---
echo "--- Llama Stack Pod Logs (last 10 lines) ---"
LS_POD=$(oc get pods -n "$NAMESPACE" -l app.kubernetes.io/name=llama-stack --no-headers 2>/dev/null | head -1 | awk '{print $1}')
if [ -z "$LS_POD" ]; then
  # fallback: try matching by name
  LS_POD=$(oc get pods -n "$NAMESPACE" --no-headers 2>/dev/null | grep llama-stack | head -1 | awk '{print $1}')
fi
if [ -n "$LS_POD" ]; then
  oc logs "$LS_POD" -n "$NAMESPACE" --tail=10 2>/dev/null || echo "  Could not fetch logs"
else
  echo "  No llama-stack pod found"
fi
echo ""

# --- 10. Quick health checks ---
echo "--- Health Checks (in-cluster) ---"
# Check if llama-stack service responds
LS_SVC=$(oc get svc -n "$NAMESPACE" --no-headers 2>/dev/null | grep llama-stack | head -1 | awk '{print $1}')
if [ -n "$LS_SVC" ]; then
  echo "  Llama Stack service: $LS_SVC"
  oc exec -n "$NAMESPACE" deploy/langflow -- curl -s --max-time 5 "http://$LS_SVC:8321/v1/health" 2>/dev/null && echo "" || echo "  Could not reach llama-stack (may still be starting)"
else
  echo "  No llama-stack service found yet (operator may still be creating it)"
fi
echo ""

echo "============================================="
echo "  Verification complete"
echo "============================================="
