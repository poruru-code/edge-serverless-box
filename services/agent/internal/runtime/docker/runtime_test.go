package docker

import (
	"context"
	"fmt"
	"io"
	"testing"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/api/types/network"
	"github.com/poruru/edge-serverless-box/services/agent/internal/runtime"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	v1 "github.com/opencontainers/image-spec/specs-go/v1"
)

type MockDockerClient struct {
	mock.Mock
}

func (m *MockDockerClient) ContainerList(ctx context.Context, options container.ListOptions) ([]types.Container, error) {
	args := m.Called(ctx, options)
	return args.Get(0).([]types.Container), args.Error(1)
}

func (m *MockDockerClient) ContainerCreate(ctx context.Context, config *container.Config, hostConfig *container.HostConfig, networkingConfig *network.NetworkingConfig, platform *v1.Platform, containerName string) (container.CreateResponse, error) {
	args := m.Called(ctx, config, hostConfig, networkingConfig, platform, containerName)
	return args.Get(0).(container.CreateResponse), args.Error(1)
}

func (m *MockDockerClient) ContainerStart(ctx context.Context, containerID string, options container.StartOptions) error {
	args := m.Called(ctx, containerID, options)
	return args.Error(0)
}

func (m *MockDockerClient) NetworkConnect(ctx context.Context, networkID, containerID string, config *network.EndpointSettings) error {
	args := m.Called(ctx, networkID, containerID, config)
	return args.Error(0)
}

func (m *MockDockerClient) ContainerInspect(ctx context.Context, containerID string) (types.ContainerJSON, error) {
	args := m.Called(ctx, containerID)
	return args.Get(0).(types.ContainerJSON), args.Error(1)
}

func (m *MockDockerClient) ContainerRemove(ctx context.Context, containerID string, options container.RemoveOptions) error {
	args := m.Called(ctx, containerID, options)
	return args.Error(0)
}

func (m *MockDockerClient) ImagePull(ctx context.Context, ref string, options image.PullOptions) (io.ReadCloser, error) {
	args := m.Called(ctx, ref, options)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(io.ReadCloser), args.Error(1)
}

func TestRuntime_Ensure_New(t *testing.T) {
	mockClient := new(MockDockerClient)
	rt := NewRuntime(mockClient, "esb-net")

	ctx := context.Background()
	req := runtime.EnsureRequest{
		FunctionName: "test-func",
		Image:        "test-image",
	}

	// 1. List: Not found
	mockClient.On("ContainerList", ctx, mock.Anything).Return([]types.Container{}, nil)

	// 2. Create
	mockClient.On("ContainerCreate", ctx, mock.Anything, mock.Anything, mock.Anything, mock.Anything, mock.Anything).
		Return(container.CreateResponse{ID: "new-id"}, nil)

	// 3. Start
	mockClient.On("ContainerStart", ctx, "new-id", mock.Anything).Return(nil)

	// 4. Inspect
	mockClient.On("ContainerInspect", ctx, "new-id").Return(types.ContainerJSON{
		NetworkSettings: &types.NetworkSettings{
			Networks: map[string]*network.EndpointSettings{
				"esb-net": {IPAddress: "10.0.0.2"},
			},
		},
	}, nil)

	// Execute
	info, err := rt.Ensure(ctx, req)

	assert.NoError(t, err)
	assert.Equal(t, "new-id", info.ID)
	assert.Equal(t, "10.0.0.2", info.IPAddress)

	mockClient.AssertExpectations(t)
}

func TestRuntime_Ensure_Exists(t *testing.T) {
	mockClient := new(MockDockerClient)
	rt := NewRuntime(mockClient, "esb-net")

	ctx := context.Background()
	req := runtime.EnsureRequest{FunctionName: "existing-func"}

	// 1. List: Found
	mockClient.On("ContainerList", ctx, mock.Anything).Return([]types.Container{
		{
			ID:     "existing-id",
			Names:  []string{"/lambda-existing-func-123"},
			Labels: map[string]string{"esb_function": "existing-func"},
			State:  "running",
		},
	}, nil)

	// 2. Network Connect
	mockClient.On("NetworkConnect", ctx, "esb-net", "existing-id", mock.Anything).Return(nil)

	// 3. Inspect
	mockClient.On("ContainerInspect", ctx, "existing-id").Return(types.ContainerJSON{
		NetworkSettings: &types.NetworkSettings{
			Networks: map[string]*network.EndpointSettings{
				"esb-net": {IPAddress: "10.0.0.3"},
			},
		},
	}, nil)

	// Execute
	info, err := rt.Ensure(ctx, req)

	assert.NoError(t, err)
	assert.Equal(t, "existing-id", info.ID)
	assert.Equal(t, "10.0.0.3", info.IPAddress)

	mockClient.AssertExpectations(t)
}

func TestRuntime_Ensure_Exists_NetworkError(t *testing.T) {
	mockClient := new(MockDockerClient)
	rt := NewRuntime(mockClient, "esb-net")

	ctx := context.Background()
	req := runtime.EnsureRequest{FunctionName: "existing-func"}

	// 1. List: Found
	mockClient.On("ContainerList", ctx, mock.Anything).Return([]types.Container{
		{
			ID:     "existing-id",
			Names:  []string{"/lambda-existing-func-123"},
			Labels: map[string]string{"esb_function": "existing-func"},
			State:  "running",
		},
	}, nil)

	// 2. Network Connect (simulate "already connected" error which should be ignored)
	mockClient.On("NetworkConnect", ctx, "esb-net", "existing-id", mock.Anything).Return(fmt.Errorf("already connected"))

	// 3. Inspect
	mockClient.On("ContainerInspect", ctx, "existing-id").Return(types.ContainerJSON{
		NetworkSettings: &types.NetworkSettings{
			Networks: map[string]*network.EndpointSettings{
				"esb-net": {IPAddress: "10.0.0.3"},
			},
		},
	}, nil)

	// Execute
	info, err := rt.Ensure(ctx, req)

	assert.NoError(t, err)
	assert.Equal(t, "existing-id", info.ID)

	mockClient.AssertExpectations(t)
}
