# Load credentials from .env
if [ -f .env ]; then
  source .env
fi
: "${CLUSTER_DOMAIN:?Set CLUSTER_DOMAIN in .env}"
: "${OC_USER:?Set OC_USER in .env}"
: "${OC_PASSWORD:?Set OC_PASSWORD in .env}"
oc login -u "$OC_USER" -p "$OC_PASSWORD" https://api.${CLUSTER_DOMAIN}:6443

# delete previous deployments if exists
oc delete deployment pocketbase -n langflow --ignore-not-found
oc delete svc pocketbase -n langflow --ignore-not-found
oc delete route pocketbase -n langflow --ignore-not-found
oc delete pvc pocketbase-data -n langflow --ignore-not-found

# clean up old llama-stack resources
oc delete llamastackdistribution llama-stack -n langflow --ignore-not-found
oc delete secret llama-stack-inference-model-secret -n langflow --ignore-not-found
oc delete deployment llama-stack -n langflow --ignore-not-found
oc delete svc llama-stack -n langflow --ignore-not-found
oc delete route llama-stack -n langflow --ignore-not-found
oc delete configmap llama-stack-config -n langflow --ignore-not-found

# ensure Llama Stack Operator is activated in RHOAI
oc patch datasciencecluster default-dsc --type=merge \
  -p '{"spec":{"components":{"llamastackoperator":{"managementState":"Managed"}}}}' || true

# deploy langflow stack (includes LlamaStackDistribution CR)
oc apply -f langflow-openshift.yaml


# oc set env deployment/swagger-ui API_URL=https://postgrest-langflow.apps.ocp.rd52l.sandbox1266.opentlc.com/
