import logging

logger = logging.getLogger("gateway.client")

# Note: OrchestratorClient has been removed as it's no longer used.
# Gateway now uses Go Agent via gRPC (GrpcProvisionClient) for container management.
# ContainerHostCache is preserved for potential future use.
