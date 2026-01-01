// Where: services/agent/cmd/agent/main_test.go
// What: Unit tests for CNI subnet overrides used by the agent startup.
// Why: Ensure the CNI config rewrite stays within the intended subnet boundaries.
package main

import (
	"encoding/json"
	"testing"
)

const sampleCNIConfig = `{
  "cniVersion": "1.0.0",
  "name": "esb-net",
  "plugins": [
    {
      "type": "bridge",
      "bridge": "esb0",
      "isGateway": true,
      "ipMasq": true,
      "ipam": {
        "type": "host-local",
        "subnet": "10.88.0.0/16",
        "routes": [{ "dst": "0.0.0.0/0" }]
      }
    },
    {
      "type": "portmap",
      "capabilities": {
        "portMappings": true
      }
    }
  ]
}`

func TestApplyCNISubnetAddsRanges(t *testing.T) {
	updated, err := applyCNISubnet([]byte(sampleCNIConfig), "10.88.1.0/24")
	if err != nil {
		t.Fatalf("applyCNISubnet returned error: %v", err)
	}

	var root map[string]any
	if err := json.Unmarshal(updated, &root); err != nil {
		t.Fatalf("failed to parse updated config: %v", err)
	}

	plugins, ok := root["plugins"].([]any)
	if !ok || len(plugins) == 0 {
		t.Fatalf("plugins missing in updated config")
	}

	var ipam map[string]any
	for _, plugin := range plugins {
		pluginMap, ok := plugin.(map[string]any)
		if !ok || pluginMap["type"] != "bridge" {
			continue
		}
		ipam, ok = pluginMap["ipam"].(map[string]any)
		if !ok {
			t.Fatalf("bridge ipam missing in updated config")
		}
		break
	}

	if ipam == nil {
		t.Fatalf("bridge plugin not found in updated config")
	}

	ranges, ok := ipam["ranges"].([]any)
	if !ok || len(ranges) != 1 {
		t.Fatalf("ranges not set as expected: %#v", ipam["ranges"])
	}

	firstRange, ok := ranges[0].([]any)
	if !ok || len(firstRange) != 1 {
		t.Fatalf("ranges entry malformed: %#v", ranges[0])
	}

	rangeMap, ok := firstRange[0].(map[string]any)
	if !ok {
		t.Fatalf("range entry malformed: %#v", firstRange[0])
	}

	if _, ok := ipam["subnet"]; ok {
		t.Fatalf("ipam subnet should be removed when ranges are set")
	}
	if rangeMap["subnet"] != "10.88.0.0/16" {
		t.Fatalf("unexpected base subnet: %#v", rangeMap["subnet"])
	}
	if rangeMap["rangeStart"] != "10.88.1.1" {
		t.Fatalf("unexpected rangeStart: %#v", rangeMap["rangeStart"])
	}
	if rangeMap["rangeEnd"] != "10.88.1.254" {
		t.Fatalf("unexpected rangeEnd: %#v", rangeMap["rangeEnd"])
	}
}

func TestApplyCNISubnetRejectsOutOfRange(t *testing.T) {
	_, err := applyCNISubnet([]byte(sampleCNIConfig), "10.99.0.0/24")
	if err == nil {
		t.Fatalf("expected error for out-of-range subnet")
	}
}
