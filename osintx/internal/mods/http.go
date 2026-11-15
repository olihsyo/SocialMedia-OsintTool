package mods

import (
	"context"
	"encoding/json"
	"io"
	"net/http"
	"time"
)

var hc = &http.Client{Timeout: 12 * time.Second}

func httpGet(ctx context.Context, u string) ([]byte, error) {
	req, _ := http.NewRequestWithContext(ctx, "GET", u, nil)
	req.Header.Set("User-Agent", "osintx/1.0")
	resp, err := hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 300 {
		return nil, nil
	}
	return io.ReadAll(io.LimitReader(resp.Body, 512*1024))
}

func httpGetAuth(ctx context.Context, u, key string) ([]byte, error) {
	req, _ := http.NewRequestWithContext(ctx, "GET", u, nil)
	req.Header.Set("hibp-api-key", key)
	req.Header.Set("User-Agent", "osintx/1.0")
	resp, err := hc.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return nil, nil
	}
	return io.ReadAll(io.LimitReader(resp.Body, 512*1024))
}

func httpStatus(ctx context.Context, u string) (int, error) {
	req, _ := http.NewRequestWithContext(ctx, "GET", u, nil)
	req.Header.Set("User-Agent", "osintx/1.0")
	resp, err := hc.Do(req)
	if err != nil {
		return 0, err
	}
	resp.Body.Close()
	return resp.StatusCode, nil
}

func jsonUnmarshal(b []byte, v any) error { return json.Unmarshal(b, v) }
