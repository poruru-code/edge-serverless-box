// Where: services/agent/internal/runtime/containerd/snapshotter_test.go
// What: Tests for containerd snapshotter selection logic.
// Why: Ensure firecracker defaults to devmapper while allowing overrides.
package containerd

import "testing"

func TestResolveSnapshotter_Override(t *testing.T) {
	t.Setenv("CONTAINERD_SNAPSHOTTER", "native")
	t.Setenv("CONTAINERD_RUNTIME", runtimeFirecracker)

	if got := resolveSnapshotter(); got != "native" {
		t.Fatalf("expected override snapshotter 'native', got %q", got)
	}
}

func TestResolveSnapshotter_FirecrackerDefault(t *testing.T) {
	t.Setenv("CONTAINERD_SNAPSHOTTER", "")
	t.Setenv("CONTAINERD_RUNTIME", runtimeFirecracker)

	if got := resolveSnapshotter(); got != snapshotterDevmapper {
		t.Fatalf("expected firecracker snapshotter %q, got %q", snapshotterDevmapper, got)
	}
}

func TestResolveSnapshotter_DefaultOverlay(t *testing.T) {
	t.Setenv("CONTAINERD_SNAPSHOTTER", "")
	t.Setenv("CONTAINERD_RUNTIME", "")

	if got := resolveSnapshotter(); got != snapshotterOverlay {
		t.Fatalf("expected default snapshotter %q, got %q", snapshotterOverlay, got)
	}
}
