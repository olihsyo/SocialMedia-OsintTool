package mods

import (
	"context"
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"net"
	"net/textproto"
	"os"
	"regexp"
	"strings"
	"time"

	"github.com/miekg/dns"
)

type Intel struct {
	Kind        string   `json:"kind"`
	Valid       bool     `json:"valid"`
	Domain      string   `json:"domain,omitempty"`
	MX          []string `json:"mx,omitempty"`
	SPF         string   `json:"spf,omitempty"`
	DMARC       string   `json:"dmarc,omitempty"`
	DKIM        []string `json:"dkim,omitempty"`
	Disposable  bool     `json:"disposable"`
	CatchAll    bool     `json:"catch_all"`
	Mailbox     string   `json:"mailbox,omitempty"`
	Gravatar    bool     `json:"gravatar"`
	PGPKeys     []string `json:"pgp_keys,omitempty"`
	Breaches    []string `json:"breaches,omitempty"`
	Reputation  string   `json:"reputation,omitempty"`
	Region      string   `json:"region,omitempty"`
	Carrier     string   `json:"carrier,omitempty"`
	Timezones   []string `json:"timezones,omitempty"`
	E164        string   `json:"e164,omitempty"`
	National    string   `json:"national,omitempty"`
	LineType    string   `json:"line_type,omitempty"`
	ValidNumber bool     `json:"valid_number"`
	Notes       []string `json:"notes,omitempty"`
}

var emailRE = regexp.MustCompile(`^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$`)

var disposable = map[string]bool{
	"mailinator.com": true, "guerrillamail.com": true, "10minutemail.com": true,
	"tempmail.com": true, "throwawaymail.com": true, "yopmail.com": true,
	"sharklasers.com": true, "trashmail.com": true, "getnada.com": true,
	"maildrop.cc": true, "dispostable.com": true, "fakeinbox.com": true,
}

func dnsTXT(ctx context.Context, name string) []string {
	c := &dns.Client{Timeout: 5 * time.Second}
	m := new(dns.Msg)
	m.SetQuestion(dns.Fqdn(name), dns.TypeTXT)
	in, _, err := c.ExchangeContext(ctx, m, "1.1.1.1:53")
	if err != nil || in == nil {
		return nil
	}
	var out []string
	for _, a := range in.Answer {
		if t, ok := a.(*dns.TXT); ok {
			out = append(out, strings.Join(t.Txt, ""))
		}
	}
	return out
}

func EmailIntel(ctx context.Context, target string, probeSMTP bool, verbose bool) *Intel {
	i := &Intel{Kind: "email"}
	target = strings.ToLower(strings.TrimSpace(target))
	i.Valid = emailRE.MatchString(target)
	if !i.Valid {
		i.Notes = append(i.Notes, "syntax invalid")
		return i
	}
	parts := strings.SplitN(target, "@", 2)
	domain := parts[1]
	i.Domain = domain
	i.Disposable = disposable[domain]

	c := &dns.Client{Timeout: 5 * time.Second}
	m := new(dns.Msg)
	m.SetQuestion(dns.Fqdn(domain), dns.TypeMX)
	if in, _, err := c.ExchangeContext(ctx, m, "1.1.1.1:53"); err == nil && in != nil {
		for _, a := range in.Answer {
			if mx, ok := a.(*dns.MX); ok {
				i.MX = append(i.MX, mx.Mx)
			}
		}
	}

	for _, t := range dnsTXT(ctx, domain) {
		if strings.HasPrefix(t, "v=spf1") {
			i.SPF = t
		}
	}
	for _, t := range dnsTXT(ctx, "_dmarc."+domain) {
		if strings.HasPrefix(t, "v=DMARC1") {
			i.DMARC = t
		}
	}
	for _, sel := range []string{"default", "google", "selector1", "selector2", "k1", "s1"} {
		for _, t := range dnsTXT(ctx, sel+"._domainkey."+domain) {
			if strings.Contains(t, "v=DKIM1") {
				i.DKIM = append(i.DKIM, sel)
			}
		}
	}
	if i.SPF == "" {
		i.Notes = append(i.Notes, "no SPF record (spoofable)")
	}

	sum := md5.Sum([]byte(target))
	if code, err := httpStatus(ctx, "https://gravatar.com/avatar/"+hex.EncodeToString(sum[:])+"?d=404"); err == nil && code == 200 {
		i.Gravatar = true
	}

	if _, err := httpGet(ctx, "https://keys.openpgp.org/vks/v1/by-email/"+target); err == nil {
		i.PGPKeys = append(i.PGPKeys, "keys.openpgp.org")
	}

	if key := os.Getenv("HIBP_API_KEY"); key != "" {
		if body, err := httpGetAuth(ctx, "https://haveibeenpwned.com/api/v3/breachedaccount/"+target+"?truncateResponse=true", key); err == nil {
			var b []struct {
				Name string `json:"Name"`
			}
			if jsonUnmarshal(body, &b) == nil {
				for _, x := range b {
					i.Breaches = append(i.Breaches, x.Name)
				}
			}
		}
	}

	if body, err := httpGet(ctx, "https://emailrep.io/"+target); err == nil {
		var er struct {
			Reputation string `json:"reputation"`
		}
		if jsonUnmarshal(body, &er) == nil && er.Reputation != "" {
			i.Reputation = er.Reputation
		}
	}

	if probeSMTP && len(i.MX) > 0 {
		i.CatchAll = smtpCatchAll(ctx, i.MX[0], domain)
		if !i.CatchAll {
			v, ev := smtpProbe(ctx, i.MX[0], target)
			i.Mailbox = ev
			if v == "EXISTS" {
				i.Notes = append(i.Notes, "mailbox accepts RCPT (likely live)")
			}
		} else {
			i.Notes = append(i.Notes, "catch-all domain: SMTP cannot confirm mailbox")
		}
	}
	return i
}

func smtpSession(ctx context.Context, mx string) (*textproto.Conn, func()) {
	d := net.Dialer{Timeout: 8 * time.Second}
	conn, err := d.DialContext(ctx, "tcp", mx+":25")
	if err != nil {
		return nil, func() {}
	}
	tp := textproto.NewConn(conn)
	if _, _, err := tp.ReadResponse(220); err != nil {
		conn.Close()
		return nil, func() {}
	}
	_ = tp.PrintfLine("EHLO osintx.local")
	for {
		code, _, err := tp.ReadResponse(250)
		if err != nil || code == 250 {
			break
		}
	}
	return tp, func() { _ = tp.PrintfLine("QUIT"); conn.Close() }
}

func smtpCatchAll(ctx context.Context, mx, domain string) bool {
	tp, done := smtpSession(ctx, mx)
	if tp == nil {
		return false
	}
	defer done()
	_ = tp.PrintfLine("MAIL FROM:<probe@example.com>")
	_, _, _ = tp.ReadResponse(250)
	rnd := fmt.Sprintf("zz%d@%s", time.Now().UnixNano(), domain)
	_ = tp.PrintfLine("RCPT TO:<%s>", rnd)
	code, _, err := tp.ReadResponse(250)
	return err == nil && (code == 250 || code == 251)
}

func smtpProbe(ctx context.Context, mx, target string) (string, string) {
	tp, done := smtpSession(ctx, mx)
	if tp == nil {
		return "UNKNOWN", "smtp connect failed"
	}
	defer done()
	_ = tp.PrintfLine("MAIL FROM:<probe@example.com>")
	_, _, _ = tp.ReadResponse(250)
	_ = tp.PrintfLine("RCPT TO:<%s>", target)
	code, msg, err := tp.ReadResponse(250)
	if err != nil {
		return "UNKNOWN", err.Error()
	}
	if code == 250 || code == 251 {
		return "EXISTS", fmt.Sprintf("RCPT %d", code)
	}
	return "ABSENT", fmt.Sprintf("RCPT %d %s", code, strings.TrimSpace(msg))
}
