#https://llamastack.github.io/docs/deploying/kubernetes_deployment
# 1.Install Kubernetes Operator
# Install the Llama Stack Kubernetes operator to manage Llama Stack deployments:
# Install from the latest main branch
kubectl apply -f https://raw.githubusercontent.com/llamastack/llama-stack-k8s-operator/main/release/operator.yaml
# Or install a specific version (e.g., v0.4.0)
# kubectl apply -f https://raw.githubusercontent.com/llamastack/llama-stack-k8s-operator/v0.4.0/release/operator.yaml

# 2.Deploy Llama Stack Server using Operator
# The operator will automatically create the necessary Deployment, Service, and other resources.
kubectl apply -f ./llamastackdistribution.yml

# 3. Checkpoint
kubectl get llamastackdistribution
echo "-------------------------------------------------"
kubectl describe llamastackdistribution llamastack-vllm
echo "-------------------------------------------------"
# Check the status of the LlamaStackDistribution
kubectl get llamastackdistribution llamastack-vllm
echo "-------------------------------------------------"
# Check the pods created by the operator
kubectl get pods -l app.kubernetes.io/name=llama-stack
echo "-------------------------------------------------"
# Wait for the pod to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=llama-stack --timeout=300s
echo "-------------------------------------------------"
# List services to find the service name
kubectl get services | grep llamastack
echo "-------------------------------------------------"
# Port forward and test (replace SERVICE_NAME with the actual service name)
kubectl port-forward service/llamastack-vllm-service 8321:8321