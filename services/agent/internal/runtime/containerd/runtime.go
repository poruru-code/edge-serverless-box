package containerd

import (
	"context"

	_ "github.com/containerd/containerd"
	_ "github.com/containerd/go-cni"
	_ "github.com/containernetworking/cni/libcni"
	_ "github.com/opencontainers/runtime-spec/specs-go"
	"github.com/poruru/edge-serverless-box/services/agent/internal/runtime"
)

type Runtime struct {
}

func NewRuntime() *Runtime {
	return &Runtime{}
}

func (r *Runtime) Ensure(ctx context.Context, req runtime.EnsureRequest) (*runtime.WorkerInfo, error) {
	return nil, nil
}

func (r *Runtime) Destroy(ctx context.Context, id string) error {
	return nil
}

func (r *Runtime) Pause(ctx context.Context, id string) error {
	return nil
}

func (r *Runtime) Resume(ctx context.Context, id string) error {
	return nil
}

func (r *Runtime) Close() error {
	return nil
}
