package engine

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

type cacheEntry struct {
	At     time.Time `json:"at"`
	Result Result    `json:"result"`
}

func cacheDir() string {
	h, _ := os.UserHomeDir()
	d := filepath.Join(h, ".osintx", "cache")
	_ = os.MkdirAll(d, 0o700)
	return d
}

func cacheKey(site, target string) string {
	sum := sha256.Sum256([]byte(site + "|" + target))
	return filepath.Join(cacheDir(), hex.EncodeToString(sum[:8])+".json")
}

func CacheGet(site, target string, ttl time.Duration) (Result, bool) {
	raw, err := os.ReadFile(cacheKey(site, target))
	if err != nil {
		return Result{}, false
	}
	var e cacheEntry
	if json.Unmarshal(raw, &e) != nil || time.Since(e.At) > ttl {
		return Result{}, false
	}
	return e.Result, true
}

func CachePut(site, target string, r Result) {
	raw, _ := json.Marshal(cacheEntry{At: time.Now(), Result: r})
	_ = os.WriteFile(cacheKey(site, target), raw, 0o600)
}
