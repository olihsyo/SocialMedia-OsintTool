package engine

import (
	"context"
	"crypto/md5"
	"encoding/hex"
	"io"
	"math/rand"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"sync"
	"time"
)

type Verdict string

const (
	VExists  Verdict = "EXISTS"
	VAbsent  Verdict = "ABSENT"
	VBlocked Verdict = "BLOCKED"
	VUnknown Verdict = "UNKNOWN"
)

type Result struct {
	Name       string  `json:"name"`
	URL        string  `json:"url"`
	Verdict    Verdict `json:"verdict"`
	Confidence int     `json:"confidence"`
	Status     int     `json:"status"`
	Evidence   string  `json:"evidence,omitempty"`
	Note       string  `json:"note,omitempty"`
}

type Summary struct {
	Checked int `json:"checked"`
	Exists  int `json:"exists"`
	Absent  int `json:"absent"`
	Blocked int `json:"blocked"`
	Unknown int `json:"unknown"`
}

func Summarize(rs []Result) Summary {
	s := Summary{Checked: len(rs)}
	for _, r := range rs {
		switch r.Verdict {
		case VExists:
			s.Exists++
		case VAbsent:
			s.Absent++
		case VBlocked:
			s.Blocked++
		default:
			s.Unknown++
		}
	}
	return s
}

var blockSignals = []string{
	"captcha", "cf-challenge", "just a moment", "too many requests",
	"rate limit", "unusual traffic", "access denied", "are you a robot",
}

func looksBlocked(status int, body string) bool {
	if status == 429 || status == 403 || status == 503 {
		return true
	}
	low := strings.ToLower(body)
	for _, s := range blockSignals {
		if strings.Contains(low, s) {
			return true
		}
	}
	return false
}

func expand(raw, target, kind string) string {
	out := strings.ReplaceAll(raw, "%s", url.QueryEscape(target))
	if strings.Contains(out, "%HASH%") {
		sum := md5.Sum([]byte(strings.ToLower(strings.TrimSpace(target))))
		out = strings.ReplaceAll(out, "%HASH%", hex.EncodeToString(sum[:]))
	}
	return out
}

func check(ctx context.Context, p *Pool, s Site, target, kind string) Result {
	r := Result{Name: s.Name, URL: expand(s.URL, target, kind), Note: s.Note}

	body := strings.ReplaceAll(s.Body, "%s", target)
	req, err := http.NewRequestWithContext(ctx, s.Method, r.URL, strings.NewReader(body))
	if err != nil {
		r.Verdict, r.Confidence, r.Evidence = VUnknown, 0, "build error"
		return r
	}
	req.Header.Set("User-Agent", RandomUA())
	req.Header.Set("Accept-Language", "en-US,en;q=0.9")
	for k, v := range s.Headers {
		req.Header.Set(k, v)
	}

	resp, err := p.Get().Do(req)
	if err != nil {
		r.Verdict, r.Confidence, r.Evidence = VUnknown, 0, err.Error()
		return r
	}
	defer resp.Body.Close()

	bs, _ := io.ReadAll(io.LimitReader(resp.Body, 256*1024))
	text := string(bs)
	r.Status = resp.StatusCode

	if looksBlocked(resp.StatusCode, text) {
		r.Verdict, r.Confidence, r.Evidence = VBlocked, 0, "anti-bot / rate limit"
		return r
	}

	hit := false
	switch s.Type {
	case "status":
		hit = resp.StatusCode == 200
	case "redirect":
		loc := resp.Header.Get("Location")
		hit = strings.Contains(loc, s.Expect)
		r.Evidence = loc
	case "absent_regex":
		re := regexp.MustCompile(s.Expect)
		hit = !re.MatchString(text)
	case "json", "regex":
		re := regexp.MustCompile(s.Expect)
		hit = re.MatchString(text)
		if hit {
			r.Evidence = re.FindString(text)
		}
	}

	if hit {
		r.Verdict = VExists
		r.Confidence = clamp(s.Weight + 1)
	} else {
		r.Verdict = VAbsent
		r.Confidence = clamp(s.Weight)
	}
	return r
}

func clamp(v int) int {
	if v < 1 {
		return 1
	}
	if v > 10 {
		return 10
	}
	return v
}

type LiveCallback func(r Result, currentURL string, isDone bool)

func Enumerate(ctx context.Context, p *Pool, sites []Site, target, kind string, conc int, verbose bool, cb LiveCallback) []Result {
	jobs := make(chan Site)
	var mu sync.Mutex
	var out []Result
	var wg sync.WaitGroup

	for i := 0; i < conc; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for s := range jobs {
				select {
				case <-ctx.Done():
					return
				default:
				}
				time.Sleep(time.Duration(rand.Intn(100)) * time.Millisecond)
				
				expandedURL := expand(s.URL, target, kind)
				
				// স্ক্যানিং শুরু
				if cb != nil {
					cb(Result{Name: s.Name}, expandedURL, false)
				}
				
				r := check(ctx, p, s, target, kind)
				
				mu.Lock()
				out = append(out, r)
				mu.Unlock()
				
				// স্ক্যানিং শেষ
				if cb != nil {
					cb(r, expandedURL, true)
				}
			}
		}()
	}

	for _, s := range sites {
		match := false
		for _, k := range s.Kinds {
			if k == kind {
				match = true
				break
			}
		}
		if match {
			jobs <- s
		}
	}
	close(jobs)
	wg.Wait()
	return out
}
