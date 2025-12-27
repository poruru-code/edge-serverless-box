package runtime

import (
	"context"
)

// EnsureRequest represents the parameters for ensuring a container is running.
type EnsureRequest struct {
	FunctionName string
	Image        string
	Env          map[string]string
}

// WorkerInfo contains the identification and connection details of a managed container.
type WorkerInfo struct {
	ID        string
	IPAddress string
	Port      int // Port used for communication (especially important for containerd NAT)
}

// ContainerRuntime defines the interface for interacting with container backends.
type ContainerRuntime interface {
	// Ensure ensures that a container for the given request is running and ready.
	Ensure(ctx context.Context, req EnsureRequest) (*WorkerInfo, error)

	// Destroy removes the specified container and its associated resources.
	Destroy(ctx context.Context, id string) error

	// Pause suspends the container's processes.
	Pause(ctx context.Context, id string) error

	// Resume un-suspends a previously paused container.
	Resume(ctx context.Context, id string) error

	// Close cleans up runtime-wide resources (e.g. connections).
	Close() error
}
