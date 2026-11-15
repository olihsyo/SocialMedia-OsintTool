package engine

import (
	"crypto/tls"
	"math/rand"
	"net"
	"net/http"
	"net/url"
	"sync/atomic"
	"time"
)

var uas = []string{
	"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
	"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
	"Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
	"Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
}

func RandomUA() string { return uas[rand.Intn(len(uas))] }

// Pool rotates across a direct client plus any configured proxies.
type Pool struct {
	clients []*http.Client
	rr      uint64
}

func NewPool(conc int, proxies []string, tor bool) *Pool {
	if tor {
		proxies = append(proxies, "socks5://127.0.0.1:9050")
	}
	p := &Pool{}
	build := func(proxy string) *http.Client {
		tr := &http.Transport{
			TLSClientConfig:     &tls.Config{InsecureSkipVerify: true},
			MaxIdleConns:        conc * 4,
			MaxIdleConnsPerHost: 4,
			IdleConnTimeout:     25 * time.Second,
			ForceAttemptHTTP2:   true,
			DialContext: (&net.Dialer{
				Timeout:   8 * time.Second,
				KeepAlive: 20 * time.Second,
			}).DialContext,
		}
		if proxy != "" {
			if u, err := url.Parse(proxy); err == nil {
				tr.Proxy = http.ProxyURL(u)
			}
		}
		return &http.Client{
			Transport: tr,
			Timeout:   15 * time.Second,
			CheckRedirect: func(r *http.Request, via []*http.Request) error {
				if len(via) >= 6 {
					return http.ErrUseLastResponse
				}
				return nil
			},
		}
	}
	p.clients = append(p.clients, build(""))
	for _, px := range proxies {
		p.clients = append(p.clients, build(px))
	}
	return p
}

func (p *Pool) Get() *http.Client {
	if len(p.clients) == 1 {
		return p.clients[0]
	}
	n := atomic.AddUint64(&p.rr, 1)
	return p.clients[n%uint64(len(p.clients))]
}
